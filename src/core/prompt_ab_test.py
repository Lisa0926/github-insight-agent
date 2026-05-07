# -*- coding: utf-8 -*-
"""
Prompt A/B testing framework for comparing prompt variants.

Provides:
- PromptExperiment: defines two prompt variants (A/B), collects performance data
- PromptABTester: manages experiments, runs comparisons, produces reports
- Integration with feedback scores for automated winner determination

Usage:
    from src.core.prompt_ab_test import PromptABTester

    tester = PromptABTester()
    exp = tester.create_experiment(
        agent_key="researcher",
        prompt_a="Old prompt text...",
        prompt_b="New prompt text...",
        description="Tighter out-of-scope constraints",
    )
    # After collecting feedback:
    report = tester.get_report(exp.id)
    print(report)
"""

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    CONCLUDED = "concluded"


class Winner(str, Enum):
    A = "A"
    B = "B"
    TIE = "tie"


@dataclass
class FeedbackObservation:
    """Single feedback data point for an experiment variant."""

    experiment_id: str
    variant: str  # "A" or "B"
    score: float  # 1.0 = good, 0.0 = bad, 0.5 = neutral
    rating: str  # "good", "bad", "neutral"
    timestamp: str
    reason: str = ""


@dataclass
class PromptExperiment:
    """A/B test experiment definition."""

    id: str
    agent_key: str
    prompt_key: str
    prompt_a: str
    prompt_b: str
    description: str
    status: str
    created_at: str
    observations: List[FeedbackObservation] = field(default_factory=list)
    winner: Optional[str] = None
    conclusion_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PromptExperiment":
        data = data.copy()
        data["observations"] = [
            FeedbackObservation(**o) for o in data.get("observations", [])
        ]
        return PromptExperiment(**data)


@dataclass
class ExperimentReport:
    """Report for a single A/B experiment."""

    experiment_id: str
    agent_key: str
    description: str
    status: str
    winner: Optional[str]
    variant_a: Dict[str, Any]
    variant_b: Dict[str, Any]
    recommendation: str


class PromptABTester:
    """
    Manages prompt A/B experiments.

    Features:
    - Create experiments with two prompt variants
    - Record feedback observations tagged by variant
    - Automated winner determination when minimum observations met
    - Report generation with statistical comparison
    """

    MIN_OBSERVATIONS = 5
    SIGNIFICANCE_THRESHOLD = 0.15  # min difference in avg score

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "data",
            "prompt_ab_tests.json",
        )
        self._experiments: Dict[str, PromptExperiment] = {}
        self._load()

    def create_experiment(
        self,
        agent_key: str,
        prompt_a: str,
        prompt_b: str,
        prompt_key: str = "system_prompt",
        description: str = "",
    ) -> PromptExperiment:
        """
        Create a new A/B experiment.

        Args:
            agent_key: Agent identifier
            prompt_a: Control prompt
            prompt_b: Test prompt
            prompt_key: Prompt field name
            description: Human-readable description of what differs

        Returns:
            PromptExperiment record
        """
        exp_id = str(uuid.uuid4())[:8]
        prompt_hash_a = hashlib.sha256(prompt_a.encode()).hexdigest()[:8]
        prompt_hash_b = hashlib.sha256(prompt_b.encode()).hexdigest()[:8]

        experiment = PromptExperiment(
            id=exp_id,
            agent_key=agent_key,
            prompt_key=prompt_key,
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            description=description or f"Compare prompt variants for {agent_key}",
            status=ExperimentStatus.DRAFT.value,
            created_at=datetime.now().isoformat(),
        )

        self._experiments[exp_id] = experiment
        logger.info(
            f"Created A/B experiment {exp_id}: {agent_key} "
            f"(hash={prompt_hash_a} vs {prompt_hash_b})"
        )
        self._save()
        return experiment

    def start_experiment(self, experiment_id: str) -> bool:
        """Mark experiment as running."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False
        exp.status = ExperimentStatus.RUNNING.value
        self._save()
        return True

    def record_observation(
        self,
        experiment_id: str,
        variant: str,
        score: float,
        rating: str,
        reason: str = "",
    ) -> bool:
        """
        Record a feedback observation for one variant.

        Args:
            experiment_id: Experiment ID
            variant: "A" or "B"
            score: Numeric score (1.0=good, 0.0=bad)
            rating: "good", "bad", or "neutral"
            reason: Optional reason string

        Returns:
            True if recorded successfully
        """
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING.value:
            logger.debug(f"Experiment {experiment_id} not running, observation skipped")
            return False

        obs = FeedbackObservation(
            experiment_id=experiment_id,
            variant=variant,
            score=score,
            rating=rating,
            timestamp=datetime.now().isoformat(),
            reason=reason,
        )
        exp.observations.append(obs)
        logger.debug(
            f"Recorded observation for {experiment_id} variant {variant} "
            f"(score={score}, total={len(exp.observations)})"
        )

        # Auto-conclude if enough data
        self._try_conclude(exp)
        self._save()
        return True

    def get_experiment(self, experiment_id: str) -> Optional[PromptExperiment]:
        return self._experiments.get(experiment_id)

    def get_active_experiment(self, agent_key: str) -> Optional[PromptExperiment]:
        """Get the currently running experiment for an agent."""
        for exp in self._experiments.values():
            if exp.agent_key == agent_key and exp.status == ExperimentStatus.RUNNING.value:
                return exp
        return None

    def get_report(self, experiment_id: str) -> Optional[ExperimentReport]:
        """Generate a report for an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None

        a_obs = [o for o in exp.observations if o.variant == "A"]
        b_obs = [o for o in exp.observations if o.variant == "B"]

        a_avg = sum(o.score for o in a_obs) / len(a_obs) if a_obs else None
        b_avg = sum(o.score for o in b_obs) / len(b_obs) if b_obs else None

        a_good = sum(1 for o in a_obs if o.rating == "good")
        b_good = sum(1 for o in b_obs if o.rating == "good")

        recommendation = ""
        if exp.winner:
            if exp.winner == Winner.TIE.value:
                recommendation = "No clear winner. Both prompts perform similarly."
            else:
                recommendation = f"Variant {exp.winner} is the winner. Consider promoting it to the default prompt."

        return ExperimentReport(
            experiment_id=exp.id,
            agent_key=exp.agent_key,
            description=exp.description,
            status=exp.status,
            winner=exp.winner,
            variant_a={
                "count": len(a_obs),
                "avg_score": round(a_avg, 3) if a_avg is not None else None,
                "good_count": a_good,
                "good_rate": round(a_good / len(a_obs), 3) if a_obs else None,
            },
            variant_b={
                "count": len(b_obs),
                "avg_score": round(b_avg, 3) if b_avg is not None else None,
                "good_count": b_good,
                "good_rate": round(b_good / len(b_obs), 3) if b_obs else None,
            },
            recommendation=recommendation,
        )

    def get_all_reports(self) -> List[ExperimentReport]:
        """Get reports for all experiments."""
        return [self.get_report(eid) for eid in self._experiments]

    def _try_conclude(self, exp: PromptExperiment) -> None:
        """Auto-conclude if minimum observations met and difference is significant."""
        a_obs = [o for o in exp.observations if o.variant == "A"]
        b_obs = [o for o in exp.observations if o.variant == "B"]

        if len(a_obs) < self.MIN_OBSERVATIONS or len(b_obs) < self.MIN_OBSERVATIONS:
            return

        a_avg = sum(o.score for o in a_obs) / len(a_obs)
        b_avg = sum(o.score for o in b_obs) / len(b_obs)
        diff = a_avg - b_avg

        if abs(diff) < self.SIGNIFICANCE_THRESHOLD:
            exp.winner = Winner.TIE.value
            logger.info(f"Experiment {exp.id}: tie (A={a_avg:.3f}, B={b_avg:.3f})")
        elif diff < 0:
            exp.winner = Winner.B.value
            logger.info(f"Experiment {exp.id}: B wins (A={a_avg:.3f}, B={b_avg:.3f})")
        else:
            exp.winner = Winner.A.value
            logger.info(f"Experiment {exp.id}: A wins (A={a_avg:.3f}, B={b_avg:.3f})")

        exp.status = ExperimentStatus.CONCLUDED.value
        exp.conclusion_at = datetime.now().isoformat()

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {k: v.to_dict() for k, v in self._experiments.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save A/B tests: {e}")

    def _load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._experiments = {
                k: PromptExperiment.from_dict(v) for k, v in data.items()
            }
        except Exception as e:
            logger.warning(f"Failed to load A/B tests: {e}")
            self._experiments = {}
