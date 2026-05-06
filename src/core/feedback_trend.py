# -*- coding: utf-8 -*-
"""
Feedback trend analyzer for GIA.

Reads from the existing feedback table (shared with FeedbackCollector)
and provides trend analysis for the north-star metric: user positive feedback rate.

Provides:
- Daily / weekly trend aggregation
- North star metric (cumulative positive feedback rate)
- Report quality statistics correlated with feedback
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from src.core.logger import get_logger

logger = get_logger(__name__)


class FeedbackTrendAnalyzer:
    """Analyzes feedback trends from the feedback table."""

    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def get_daily_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Return daily feedback aggregation for the last N days.

        Each entry contains: date, total, good, bad, neutral, positive_rate.
        """
        conn = self._get_connection()
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            rows = conn.execute(
                """
                SELECT
                    substr(timestamp, 1, 10) AS date,
                    COUNT(*) AS total,
                    SUM(CASE WHEN rating = 'good' THEN 1 ELSE 0 END) AS good,
                    SUM(CASE WHEN rating = 'bad' THEN 1 ELSE 0 END) AS bad,
                    SUM(CASE WHEN rating = 'neutral' THEN 1 ELSE 0 END) AS neutral
                FROM feedback
                WHERE substr(timestamp, 1, 10) >= ?
                GROUP BY substr(timestamp, 1, 10)
                ORDER BY date ASC
                """,
                (cutoff,),
            ).fetchall()
            result = []
            for row in rows:
                r = dict(row)
                positive_rate = round(r["good"] / r["total"] * 100, 1) if r["total"] > 0 else 0.0
                result.append({
                    "date": r["date"],
                    "total": r["total"],
                    "good": r["good"],
                    "bad": r["bad"],
                    "neutral": r["neutral"],
                    "positive_rate": positive_rate,
                })
            return result
        except Exception as e:
            logger.warning(f"Failed to compute daily trends: {e}")
            return []
        finally:
            conn.close()

    def get_north_star_metric(self) -> Dict[str, Any]:
        """
        Return the north-star metric: overall positive feedback rate.

        Also breaks down by time windows (7d, 30d, all-time) and by agent.
        """
        conn = self._get_connection()
        try:
            # Overall stats
            overall = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN rating = 'good' THEN 1 ELSE 0 END) AS good,
                    SUM(CASE WHEN rating = 'bad' THEN 1 ELSE 0 END) AS bad,
                    AVG(CASE WHEN json_extract(metadata, '$.tti_total') IS NOT NULL
                        THEN json_extract(metadata, '$.tti_total') END) AS avg_tti
                FROM feedback
                """
            ).fetchone()

            # 7-day window
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            recent_7d = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN rating = 'good' THEN 1 ELSE 0 END) AS good,
                    SUM(CASE WHEN rating = 'bad' THEN 1 ELSE 0 END) AS bad
                FROM feedback
                WHERE timestamp >= ?
                """,
                (seven_days_ago,),
            ).fetchone()

            # 30-day window
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            recent_30d = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN rating = 'good' THEN 1 ELSE 0 END) AS good,
                    SUM(CASE WHEN rating = 'bad' THEN 1 ELSE 0 END) AS bad
                FROM feedback
                WHERE timestamp >= ?
                """,
                (thirty_days_ago,),
            ).fetchone()

            # By agent
            by_agent = conn.execute(
                """
                SELECT
                    agent,
                    COUNT(*) AS total,
                    SUM(CASE WHEN rating = 'good' THEN 1 ELSE 0 END) AS good,
                    SUM(CASE WHEN rating = 'bad' THEN 1 ELSE 0 END) AS bad
                FROM feedback
                GROUP BY agent
                ORDER BY total DESC
                """
            ).fetchall()

            def _rate(good, total):
                return round(good / total * 100, 1) if total > 0 else 0.0

            return {
                "overall": {
                    "total": overall["total"],
                    "good": overall["good"],
                    "bad": overall["bad"],
                    "positive_rate": _rate(overall["good"], overall["total"]),
                    "avg_tti": round(overall["avg_tti"] or 0, 2),
                },
                "recent_7d": {
                    "total": recent_7d["total"],
                    "good": recent_7d["good"],
                    "bad": recent_7d["bad"],
                    "positive_rate": _rate(recent_7d["good"], recent_7d["total"]),
                },
                "recent_30d": {
                    "total": recent_30d["total"],
                    "good": recent_30d["good"],
                    "bad": recent_30d["bad"],
                    "positive_rate": _rate(recent_30d["good"], recent_30d["total"]),
                },
                "by_agent": [
                    {
                        "agent": row["agent"],
                        "total": row["total"],
                        "good": row["good"],
                        "bad": row["bad"],
                        "positive_rate": _rate(row["good"], row["total"]),
                    }
                    for row in by_agent
                ],
            }
        except Exception as e:
            logger.warning(f"Failed to compute north star metric: {e}")
            return {"overall": {}, "recent_7d": {}, "recent_30d": {}, "by_agent": []}
        finally:
            conn.close()

    def get_report_stats(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Return recent feedback entries enriched with derived metrics.

        Useful for correlating report properties (project count, TTI) with
        user satisfaction.
        """
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, timestamp, rating, reason, agent,
                       json_extract(metadata, '$.project_count') AS project_count,
                       json_extract(metadata, '$.tti_total') AS tti_total,
                       user_input
                FROM feedback
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            result = []
            for row in rows:
                r = dict(row)
                result.append({
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "rating": r["rating"],
                    "reason": r["reason"],
                    "agent": r["agent"],
                    "project_count": r["project_count"] or 0,
                    "tti_total": round(r["tti_total"] or 0, 2),
                    "user_input": r["user_input"],
                })
            return result
        except Exception as e:
            logger.warning(f"Failed to compute report stats: {e}")
            return []
        finally:
            conn.close()

    def get_trend_summary(self) -> str:
        """
        Return a human-readable trend summary for CLI display.
        """
        north_star = self.get_north_star_metric()
        daily = self.get_daily_trends(days=7)

        lines = ["## Feedback Trend Summary"]

        overall = north_star.get("overall", {})
        if overall:
            lines.append(f"- **Total feedback**: {overall.get('total', 0)}")
            lines.append(f"- **Positive rate (all-time)**: {overall.get('positive_rate', 0)}%")
            lines.append(f"- **Avg TTI**: {overall.get('avg_tti', 0)}s")

        recent = north_star.get("recent_7d", {})
        if recent:
            lines.append(f"- **Positive rate (7d)**: {recent.get('positive_rate', 0)}% ({recent.get('total', 0)} reviews)")

        recent30 = north_star.get("recent_30d", {})
        if recent30:
            lines.append(
                f"- **Positive rate (30d)**: {recent30.get('positive_rate', 0)}%"
                f" ({recent30.get('total', 0)} reviews)"
            )

        if daily:
            lines.append("")
            lines.append("### Daily Breakdown (Last 7 Days)")
            lines.append("| Date | Total | Good | Bad | Rate |")
            lines.append("|------|-------|------|-----|------|")
            for d in daily:
                lines.append(
                    f"| {d['date']} | {d['total']} | {d['good']} | {d['bad']} | {d['positive_rate']}% |"
                )

        agents = north_star.get("by_agent", [])
        if agents:
            lines.append("")
            lines.append("### By Agent")
            for a in agents:
                lines.append(
                    f"- **{a['agent']}**: {a['positive_rate']}% positive ({a['total']} reviews)"
                )

        return "\n".join(lines)
