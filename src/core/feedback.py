# -*- coding: utf-8 -*-
"""
Feedback collector — stores user feedback for analysis and future prompt tuning

Features:
- SQLite-backed storage (reuses data/app.db)
- /rate <good|bad> [reason] — quick thumbs up/down
- /feedback "text" — free-form feedback
- Session-scoped message correlation (associates feedback with the last assistant response)

Table schema:
    feedback (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp     TEXT NOT NULL,
        run_id        TEXT,
        agent         TEXT,
        user_input    TEXT,
        assistant_output TEXT,
        rating        TEXT NOT NULL CHECK(rating IN ('good', 'bad', 'neutral')),
        reason        TEXT DEFAULT '',
        metadata      TEXT DEFAULT '{}'
    )
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)

# Schema version — used to detect when migration is needed
SCHEMA_VERSION = 1


class FeedbackCollector:
    """Stores and retrieves user feedback from SQLite."""

    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        """Create feedback table if it doesn't exist."""
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp        TEXT    NOT NULL,
                    run_id           TEXT    DEFAULT '',
                    agent            TEXT    DEFAULT '',
                    user_input       TEXT    DEFAULT '',
                    assistant_output TEXT    DEFAULT '',
                    rating           TEXT    NOT NULL CHECK(rating IN ('good', 'bad', 'neutral')),
                    reason           TEXT    DEFAULT '',
                    metadata         TEXT    DEFAULT '{}'
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        rating: str,
        reason: str = "",
        user_input: str = "",
        assistant_output: str = "",
        agent: str = "",
        run_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Record a single feedback entry.

        Returns:
            The row id of the new entry.
        """
        if rating not in ("good", "bad", "neutral"):
            raise ValueError(f"Invalid rating: {rating!r}. Must be 'good', 'bad', or 'neutral'.")

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO feedback (timestamp, run_id, agent, user_input, assistant_output, rating, reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    run_id,
                    agent,
                    user_input,
                    assistant_output,
                    rating,
                    reason,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()
            row_id = cursor.lastrowid
            logger.info(f"Feedback recorded: id={row_id}, rating={rating}")
            return row_id
        finally:
            conn.close()

    def record_quick(
        self,
        rating: str,
        reason: str = "",
        session_state: Optional["FeedbackSession"] = None,
    ) -> int:
        """
        Record feedback using session context (last input/output).

        If session_state is provided, user_input and assistant_output are
        auto-filled from the session. Otherwise only rating+reason are stored.
        """
        user_input = ""
        assistant_output = ""
        agent = ""
        run_id = ""

        if session_state:
            user_input = session_state.last_user_input or ""
            assistant_output = session_state.last_assistant_output or ""
            agent = session_state.current_agent or ""
            run_id = session_state.run_id or ""

        return self.record(
            rating=rating,
            reason=reason,
            user_input=user_input,
            assistant_output=assistant_output,
            agent=agent,
            run_id=run_id,
        )

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent feedback entries."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate feedback statistics."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN rating = 'good' THEN 1 ELSE 0 END) AS good,
                    SUM(CASE WHEN rating = 'bad' THEN 1 ELSE 0 END) AS bad,
                    SUM(CASE WHEN rating = 'neutral' THEN 1 ELSE 0 END) AS neutral
                FROM feedback
                """
            )
            row = cursor.fetchone()
            total = row[0]
            good = row[1] or 0
            bad = row[2] or 0
            neutral = row[3] or 0
            positive_rate = (good / total * 100) if total > 0 else 0.0
            return {
                "total": total,
                "good": good,
                "bad": bad,
                "neutral": neutral,
                "positive_rate": round(positive_rate, 1),
            }
        finally:
            conn.close()

    def get_positive_feedback_patterns(self, limit: int = 10) -> List[str]:
        """Extract positive feedback reason patterns for prompt injection.

        Returns a deduplicated list of reason strings from 'good' feedback entries,
        ordered by recency. These patterns can be injected into system prompts to
        reinforce behaviors the user has explicitly approved.

        Args:
            limit: Maximum number of patterns to return.

        Returns:
            List of reason strings from positive feedback.
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT DISTINCT reason
                FROM feedback
                WHERE rating = 'good' AND reason != ''
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row)["reason"].strip() for row in rows if row["reason"].strip()]
        finally:
            conn.close()


class FeedbackSession:
    """
    Lightweight session tracker that holds the most recent user input and
    assistant output so feedback can be correlated automatically.
    """

    def __init__(self, run_id: str = "", current_agent: str = ""):
        self.run_id = run_id
        self.current_agent = current_agent
        self.last_user_input: str = ""
        self.last_assistant_output: str = ""

    def set_last_interaction(self, user_input: str, assistant_output: str) -> None:
        self.last_user_input = user_input
        self.last_assistant_output = assistant_output

    def set_agent(self, agent: str) -> None:
        self.current_agent = agent


# ---- Module-level singleton (initialized when CLI starts) ----

_feedback_collector: Optional[FeedbackCollector] = None


def get_feedback_collector(db_path: str = "data/app.db") -> FeedbackCollector:
    """Return the global FeedbackCollector instance (singleton)."""
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = FeedbackCollector(db_path=db_path)
    return _feedback_collector


def reset_feedback_collector() -> None:
    """Reset singleton (for testing)."""
    global _feedback_collector
    _feedback_collector = None
