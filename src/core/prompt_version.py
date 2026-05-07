# -*- coding: utf-8 -*-
"""
Prompt version management for tracking prompt changes over time.

Provides:
- PromptVersion: stores version metadata (timestamp, change reason, hash)
- PromptVersionHistory: persists version history, detects changes, correlates with feedback
- Integration point: prompt_builder.get_system_prompt() auto-records versions

Usage:
    from src.core.prompt_version import PromptVersionManager

    manager = PromptVersionManager()
    version = manager.record_prompt("researcher", system_prompt, reason="Updated constraints")
    changes = manager.get_recent_changes(agent_key="researcher", count=5)
    diff = manager.compare_versions("researcher", v1=2, v2=3)
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PromptVersion:
    """Single prompt version record."""

    agent_key: str
    prompt_key: str
    version: int
    prompt_hash: str
    prompt_content: str
    change_reason: str
    timestamp: str
    feedback_scores: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PromptVersion":
        return PromptVersion(**data)


class PromptVersionManager:
    """
    Manages prompt version history for all agents.

    Features:
    - Records a new version whenever prompt content changes
    - Detects changes via content hash comparison
    - Correlates versions with feedback scores
    - Provides diff between any two versions
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Args:
            storage_path: JSON file for persisting version history.
                         Defaults to data/prompt_versions.json
        """
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "data",
            "prompt_versions.json",
        )
        # Key: "agent_key:prompt_key" -> List[PromptVersion]
        self._history: Dict[str, List[PromptVersion]] = {}
        self._load()

    def _make_key(self, agent_key: str, prompt_key: str) -> str:
        return f"{agent_key}:{prompt_key}"

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]

    def record_prompt(
        self,
        agent_key: str,
        prompt_content: str,
        prompt_key: str = "system_prompt",
        change_reason: str = "",
    ) -> PromptVersion:
        """
        Record a prompt version. Only creates a new version if content changed.

        Args:
            agent_key: Agent identifier (researcher / analyst / pipeline)
            prompt_content: Full prompt text
            prompt_key: Prompt field name
            change_reason: Human-readable reason for this change

        Returns:
            The PromptVersion record
        """
        key = self._make_key(agent_key, prompt_key)
        prompt_hash = self._compute_hash(prompt_content)

        history = self._history.get(key, [])
        latest = history[-1] if history else None

        # Skip if content unchanged
        if latest and latest.prompt_hash == prompt_hash:
            logger.debug(
                f"Prompt {agent_key}:{prompt_key} unchanged (v{latest.version}), "
                f"skipping version record"
            )
            return latest

        version_num = (latest.version + 1) if latest else 1
        record = PromptVersion(
            agent_key=agent_key,
            prompt_key=prompt_key,
            version=version_num,
            prompt_hash=prompt_hash,
            prompt_content=prompt_content,
            change_reason=change_reason or f"Auto-detected change from v{version_num - 1 if latest else 0}",
            timestamp=datetime.now().isoformat(),
        )

        self._history.setdefault(key, []).append(record)
        logger.info(
            f"Recorded prompt version {agent_key}:{prompt_key} v{version_num} "
            f"(hash={prompt_hash}, reason={change_reason})"
        )

        self._save()
        return record

    def get_latest(self, agent_key: str, prompt_key: str = "system_prompt") -> Optional[PromptVersion]:
        """Get the latest version for a given agent/prompt."""
        key = self._make_key(agent_key, prompt_key)
        history = self._history.get(key, [])
        return history[-1] if history else None

    def get_history(
        self, agent_key: str, prompt_key: str = "system_prompt"
    ) -> List[PromptVersion]:
        """Get full version history for a given agent/prompt."""
        key = self._make_key(agent_key, prompt_key)
        return self._history.get(key, [])

    def get_recent_changes(
        self, agent_key: Optional[str] = None, count: int = 10
    ) -> List[PromptVersion]:
        """
        Get the most recent version changes across all agents or a specific agent.

        Args:
            agent_key: Filter by agent, or None for all agents
            count: Maximum number of records to return

        Returns:
            List of PromptVersion sorted by timestamp descending
        """
        all_records: List[PromptVersion] = []
        for records in self._history.values():
            for rec in records:
                if agent_key is None or rec.agent_key == agent_key:
                    all_records.append(rec)

        all_records.sort(key=lambda r: r.timestamp, reverse=True)
        return all_records[:count]

    def compare_versions(
        self,
        agent_key: str,
        v1: int,
        v2: int,
        prompt_key: str = "system_prompt",
    ) -> Dict[str, Any]:
        """
        Compare two versions of a prompt.

        Args:
            agent_key: Agent identifier
            v1: First version number
            v2: Second version number
            prompt_key: Prompt field name

        Returns:
            Dict with keys: v1, v2, changed (bool), diff_summary (str)
        """
        key = self._make_key(agent_key, prompt_key)
        history = self._history.get(key, [])

        rec_v1 = next((r for r in history if r.version == v1), None)
        rec_v2 = next((r for r in history if r.version == v2), None)

        if not rec_v1:
            return {"error": f"Version {v1} not found for {key}"}
        if not rec_v2:
            return {"error": f"Version {v2} not found for {key}"}

        changed = rec_v1.prompt_hash != rec_v2.prompt_hash
        diff_summary = ""
        if changed:
            lines_v1 = set(rec_v1.prompt_content.splitlines())
            lines_v2 = set(rec_v2.prompt_content.splitlines())
            added = lines_v2 - lines_v1
            removed = lines_v1 - lines_v2
            diff_summary = (
                f"Added {len(added)} line(s), removed {len(removed)} line(s)."
            )
            if added:
                diff_summary += f" Added: {list(added)[:3]}"
            if removed:
                diff_summary += f" Removed: {list(removed)[:3]}"

        return {
            "v1": rec_v1.to_dict(),
            "v2": rec_v2.to_dict(),
            "changed": changed,
            "diff_summary": diff_summary,
        }

    def record_feedback(
        self,
        agent_key: str,
        prompt_key: str,
        score: float,
        timestamp: Optional[str] = None,
    ) -> None:
        """
        Correlate a feedback score with the active prompt version.

        Args:
            agent_key: Agent identifier
            prompt_key: Prompt field name
            score: Feedback score (e.g. 1.0 for good, 0.0 for bad)
            timestamp: Override timestamp (defaults to now)
        """
        key = self._make_key(agent_key, prompt_key)
        history = self._history.get(key, [])
        if not history:
            logger.debug(f"No prompt version for {key}, cannot correlate feedback")
            return

        latest = history[-1]
        latest.feedback_scores.append(score)
        logger.debug(
            f"Correlated feedback score={score} with {key} v{latest.version}"
        )
        self._save()

    def get_version_stats(
        self, agent_key: str, prompt_key: str = "system_prompt"
    ) -> Dict[str, Any]:
        """
        Get statistics for a prompt version.

        Returns:
            Dict with total_versions, current_version, current_hash,
            avg_feedback_score, feedback_count
        """
        key = self._make_key(agent_key, prompt_key)
        history = self._history.get(key, [])
        if not history:
            return {
                "total_versions": 0,
                "current_version": None,
                "current_hash": None,
                "avg_feedback_score": None,
                "feedback_count": 0,
            }

        latest = history[-1]
        scores = latest.feedback_scores
        return {
            "total_versions": len(history),
            "current_version": latest.version,
            "current_hash": latest.prompt_hash,
            "change_reason": latest.change_reason,
            "avg_feedback_score": round(sum(scores) / len(scores), 3) if scores else None,
            "feedback_count": len(scores),
        }

    def _save(self) -> None:
        """Persist version history to JSON."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                k: [r.to_dict() for r in v]
                for k, v in self._history.items()
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save prompt versions: {e}")

    def _load(self) -> None:
        """Load version history from JSON."""
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._history = {
                k: [PromptVersion.from_dict(r) for r in v]
                for k, v in data.items()
            }
            logger.info(f"Loaded prompt version history from {self.storage_path}")
        except Exception as e:
            logger.warning(f"Failed to load prompt versions: {e}")
            self._history = {}
