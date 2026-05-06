# -*- coding: utf-8 -*-
"""
KPI Tracker for GIA agents.

Reads KPI definitions from role_kpi.yaml, evaluates them using
LLM-as-Judge or rule-based scoring, and persists results to JSONL.

Also provides a shared `_load_role_kpi_config()` used by:
- GiaAgentBase._inject_role_constraints()
- get_circuit_breaker()
- This tracker

KPI Alert Manager:
- KPIAlertManager checks KPI values against targets from role_kpi.yaml
- Triggers WARNING callbacks or CRITICAL circuit breaker on threshold violations
- Use `get_alert_manager()` for the singleton instance

Usage:
    from src.core.kpi_tracker import KPITracker, get_alert_manager

    tracker = KPITracker(config)
    tracker.track_pipeline_kpis(tti_seconds=45.2, success=True, token_count=3200)

    # Check alert summary
    alert_mgr = get_alert_manager()
    print(alert_mgr.get_summary())
"""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# Shared role_kpi.yaml loader (process-level cache)
# ============================================================

_role_kpi_config_cache: Optional[Dict[str, Any]] = None


def _load_role_kpi_config() -> Optional[Dict[str, Any]]:
    """
    Load role_kpi.yaml once per process and cache it.

    Used by:
    - GiaAgentBase._inject_role_constraints()
    - get_circuit_breaker() in guardrails.py
    - KPITracker
    """
    global _role_kpi_config_cache
    if _role_kpi_config_cache is not None:
        return _role_kpi_config_cache

    kpi_path = Path(__file__).parent.parent / "config" / "role_kpi.yaml"
    try:
        with open(kpi_path, "r", encoding="utf-8") as f:
            _role_kpi_config_cache = yaml.safe_load(f)
        logger.info(f"role_kpi.yaml loaded from {kpi_path}")
    except FileNotFoundError:
        logger.warning(f"role_kpi.yaml not found at {kpi_path}")
    except Exception as e:
        logger.warning(f"Failed to load role_kpi.yaml: {e}")

    return _role_kpi_config_cache


# ============================================================
# KPI Alert Manager
# ============================================================

class KPIAlertLevel(str, Enum):
    """Alert severity levels for KPI violations."""
    INFO = "info"          # Logged but non-blocking
    WARNING = "warning"    # Logged + triggers degrade strategy
    CRITICAL = "critical"  # Triggers circuit breaker


@dataclass
class KPIAlert:
    """A single KPI threshold violation alert."""
    agent: str
    kpi_name: str
    actual_value: float
    target_value: float
    severity: KPIAlertLevel
    message: str
    timestamp: float = field(default_factory=time.time)


class KPIAlertManager:
    """
    Manages KPI threshold alerts and auto-degrade strategies.

    Checks KPI values against targets defined in role_kpi.yaml
    and triggers callbacks when violations occur.

    Degradation strategies (per severity):
    - INFO: Log only
    - WARNING: Log + notify registered callbacks (e.g., slow down rate)
    - CRITICAL: Log + trigger circuit breaker to halt execution
    """

    # Default thresholds (overridden by role_kpi.yaml when available)
    DEFAULT_THRESHOLDS: Dict[str, Dict[str, Any]] = {
        "researcher": {
            "intent_accuracy": {"min": 0.95, "severity": "warning"},
            "fetch_success_rate": {"min": 0.98, "severity": "critical"},
            "rate_limit_handled": {"min": 1.0, "severity": "warning"},
        },
        "analyst": {
            "structural_completeness": {"min": 0.6, "severity": "warning"},
            "fact_check_pass": {"min": 1.0, "severity": "critical"},
            "tech_stack_coverage": {"min": 0.67, "severity": "info"},
        },
        "pipeline": {
            "tti_score": {"min": 0.5, "severity": "warning"},
            "task_success": {"min": 1.0, "severity": "critical"},
        },
    }

    def __init__(self, config=None):
        self._callbacks: List[Callable[[KPIAlert], None]] = []
        self._violations: List[KPIAlert] = []
        self._circuit_breaker_triggered = False
        self._config = config

        # Load thresholds from role_kpi.yaml if available
        kpi_config = _load_role_kpi_config() or {}
        self._thresholds = self._build_thresholds(kpi_config)

    def _build_thresholds(self, kpi_config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Build thresholds from role_kpi.yaml, falling back to defaults."""
        thresholds = {}
        agents_config = kpi_config.get("agents", {})

        for agent_name, agent_config in agents_config.items():
            kpi_defs = agent_config.get("kpis", [])
            agent_thresholds = {}
            for kpi_def in kpi_defs:
                name = kpi_def.get("name", "")
                target = kpi_def.get("target", "")
                # Parse target string like "≥ 95%" or "≤ 60s"
                threshold = self._parse_target(target)
                if threshold is not None:
                    agent_thresholds[name] = threshold
            if agent_thresholds:
                thresholds[agent_name] = agent_thresholds

        # Merge with defaults for any missing keys
        for agent, defaults in self.DEFAULT_THRESHOLDS.items():
            if agent not in thresholds:
                thresholds[agent] = defaults
            else:
                for kpi, cfg in defaults.items():
                    if kpi not in thresholds[agent]:
                        thresholds[agent][kpi] = cfg

        return thresholds

    def _parse_target(self, target_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse a KPI target string into a threshold config.

        Examples:
            "≥ 95%"  → {"min": 0.95, "severity": "warning"}
            "≤ 60s"  → {"max": 60.0, "severity": "warning"}
            "100% 拦截不崩溃" → {"min": 1.0, "severity": "warning"}
            "≥ 4.5 / 5.0" → {"min": 0.9, "severity": "warning"}
        """
        target_str = target_str.strip()

        import re
        # Pattern: ≥ XX% or ≤ XX%
        pct_match = re.match(r"[≥>=]+\s*(\d+(?:\.\d+)?)\s*%", target_str)
        if pct_match:
            val = float(pct_match.group(1)) / 100.0
            return {"min": val, "severity": "warning"}

        # Pattern: ≤ XXs or ≤ XX (seconds / time threshold)
        time_match = re.match(r"[≤<=]+\s*(\d+(?:\.\d+)?)\s*s", target_str)
        if time_match:
            return {"max": float(time_match.group(1)), "severity": "warning"}

        # Pattern: ≤ XX (numeric upper bound, e.g. cost)
        num_upper = re.match(r"[≤<=]+\s*(\d+(?:\.\d+)?)", target_str)
        if num_upper:
            return {"max": float(num_upper.group(1)), "severity": "info"}

        # Pattern: ≥ XX / YY (ratio, e.g. "≥ 4.5 / 5.0")
        ratio_match = re.match(r"[≥>=]+\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", target_str)
        if ratio_match:
            numerator = float(ratio_match.group(1))
            denominator = float(ratio_match.group(2))
            return {"min": numerator / denominator, "severity": "warning"}

        return None

    def register_callback(self, callback: Callable[[KPIAlert], None]) -> None:
        """Register a callback to be invoked on WARNING/CRITICAL violations."""
        self._callbacks.append(callback)

    def check_kpi(
        self,
        agent: str,
        kpi_name: str,
        value: float,
    ) -> Optional[KPIAlert]:
        """
        Check a single KPI value against its threshold.

        Returns:
            KPIAlert if threshold is violated, None otherwise.
        """
        agent_thresholds = self._thresholds.get(agent, {})
        kpi_threshold = agent_thresholds.get(kpi_name)
        if not kpi_threshold:
            return None

        severity = KPIAlertLevel(kpi_threshold.get("severity", "info"))
        target_min = kpi_threshold.get("min")
        target_max = kpi_threshold.get("max")

        violated = False
        target_value = None

        if target_min is not None and value < target_min:
            violated = True
            target_value = target_min
        elif target_max is not None and value > target_max:
            violated = True
            target_value = target_max

        if not violated:
            return None

        alert = KPIAlert(
            agent=agent,
            kpi_name=kpi_name,
            actual_value=value,
            target_value=target_value,
            severity=severity,
            message=f"KPI violation [{agent}.{kpi_name}]: actual={value}, target={'<=' if target_max else '>='} {target_value}",
        )

        self._violations.append(alert)
        logger.warning(f"[KPI_ALERT] {alert.message} (severity={severity.value})")

        # Trigger callbacks for WARNING and CRITICAL
        if severity in (KPIAlertLevel.WARNING, KPIAlertLevel.CRITICAL):
            for callback in self._callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.warning(f"KPI alert callback failed: {e}")

        # Auto-trigger circuit breaker on CRITICAL
        if severity == KPIAlertLevel.CRITICAL:
            self._circuit_breaker_triggered = True
            self._trigger_circuit_breaker(agent, kpi_name)

        return alert

    def _trigger_circuit_breaker(self, agent: str, kpi_name: str) -> None:
        """Trigger the agent circuit breaker for CRITICAL violations."""
        try:
            from src.core.guardrails import get_circuit_breaker
            cb = get_circuit_breaker()
            # Force-open the circuit breaker with a descriptive reason
            if not cb.is_open:
                cb._open = True
                cb._reason = f"KPI CRITICAL: {agent}.{kpi_name} threshold violated"
                logger.critical(f"Circuit breaker triggered by KPI alert: {cb._reason}")
        except Exception as e:
            logger.warning(f"Failed to trigger circuit breaker: {e}")

    def reset(self) -> None:
        """Clear all violations and circuit breaker flag."""
        self._violations.clear()
        self._circuit_breaker_triggered = False

    @property
    def violations(self) -> List[KPIAlert]:
        return list(self._violations)

    @property
    def circuit_breaker_triggered(self) -> bool:
        return self._circuit_breaker_triggered

    def get_summary(self) -> Dict[str, Any]:
        """Get alert summary for reporting."""
        return {
            "total_violations": len(self._violations),
            "circuit_breaker_triggered": self._circuit_breaker_triggered,
            "violations_by_agent": {
                agent: sum(1 for v in self._violations if v.agent == agent)
                for agent in set(v.agent for v in self._violations)
            },
            "violations_by_severity": {
                level.value: sum(1 for v in self._violations if v.severity == level)
                for level in KPIAlertLevel
            },
        }


# Global alert manager singleton
_global_alert_manager: Optional[KPIAlertManager] = None


def get_alert_manager() -> KPIAlertManager:
    """Get or create the global KPI alert manager."""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = KPIAlertManager()
    return _global_alert_manager


# ============================================================
# KPI Tracker
# ============================================================

class KPITracker:
    """
    Tracks agent KPIs as defined in role_kpi.yaml.

    Evaluates KPIs using:
    - Rule-based scoring (structural KPIs)
    - LLM-as-Judge (quality KPIs)
    - Timestamps (TTI KPIs)

    Persists results to ~/.hermes/gia_metrics.jsonl
    """

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        metrics_path: Optional[str] = None,
        alert_manager: Optional[KPIAlertManager] = None,
    ):
        self.config = config or ConfigManager()
        self._run_id: str = str(int(time.time()))

        if metrics_path:
            self.metrics_path = Path(metrics_path)
        else:
            self.metrics_path = Path.home() / ".hermes" / "gia_metrics.jsonl"

        self.alert_manager = alert_manager or get_alert_manager()

    @property
    def run_id(self) -> str:
        return self._run_id

    @run_id.setter
    def run_id(self, value: str) -> None:
        self._run_id = value

    # ---- Researcher KPIs ----

    def track_researcher_kpis(
        self,
        intent_action: str,
        intent_params: Dict[str, Any],
        success: bool,
        api_429_count: int = 0,
        result_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Track ResearcherAgent KPIs:
        - 意图解析准确率: whether the LLM selected the correct action
        - 数据获取成功率: (successes - 429 failures) / total requests
        - API限流优雅降级: whether 429s are handled without crashes
        """
        kpis = {}

        # Intent accuracy: heuristic — if action is one of the expected types
        expected_actions = {"search_repositories", "get_repo_info", "analyze_project", "compare_repositories", "chat"}
        kpis["intent_accuracy"] = 1.0 if intent_action in expected_actions else 0.0

        # Data fetch success rate
        if result_count > 0:
            kpis["fetch_success_rate"] = 1.0
        elif success and result_count == 0:
            kpis["fetch_success_rate"] = 0.5  # Empty result, not an error
        else:
            kpis["fetch_success_rate"] = 0.0

        # API rate limit handling
        kpis["rate_limit_handled"] = api_429_count == 0 or success

        self._persist("researcher", kpis)

        # Check KPI thresholds
        self._check_kpi_numeric("researcher", "intent_accuracy", kpis["intent_accuracy"])
        self._check_kpi_numeric("researcher", "fetch_success_rate", kpis["fetch_success_rate"])
        self._check_kpi_bool("researcher", "rate_limit_handled", kpis["rate_limit_handled"])

        logger.info(f"Researcher KPIs: {kpis}")
        return kpis

    # ---- Analyst KPIs ----

    def track_analyst_kpis(
        self,
        analysis: Dict[str, Any],
        report_text: str,
        model_fn=None,
    ) -> Dict[str, Any]:
        """
        Track AnalystAgent KPIs:
        - 分析客观性评分: via LLMJudgeMetric (if model_fn provided)
        - 幻觉/事实错误率: structural check (has required fields)
        - 技术栈识别覆盖率: presence of tech_stack and architecture_pattern
        """
        kpis = {}

        # Objective scoring (rule-based structural check)
        required_fields = ["core_function", "tech_stack", "architecture_pattern", "pain_points", "risk_flags"]
        present = sum(1 for f in required_fields if analysis.get(f))
        kpis["structural_completeness"] = present / len(required_fields)

        # Fact check (hallucination proxy): does output have numeric data?
        has_stars = analysis.get("stars") is not None
        has_language = bool(analysis.get("language"))
        kpis["fact_check_pass"] = has_stars and has_language

        # Tech stack coverage
        tech_stack = analysis.get("tech_stack", [])
        kpis["tech_stack_coverage"] = min(len(tech_stack) / 3.0, 1.0) if isinstance(tech_stack, list) else 0.0

        # If LLM-as-Judge model is available, do quality scoring
        if model_fn:
            try:
                from src.core.llm_judge import LLMJudgeMetric
                from agentscope.evaluate._solution import SolutionOutput

                metric = LLMJudgeMetric(model_fn=model_fn)
                solution = SolutionOutput(
                    success=True,
                    output=report_text,
                    trajectory=[],
                )
                # Use asyncio for async metric
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    metric(solution, task_input="Analyze this GitHub project")
                )
                kpis["llm_judge_score"] = result.result
            except Exception as e:
                logger.warning(f"LLM-as-Judge scoring failed: {e}")
                kpis["llm_judge_score"] = None

        self._persist("analyst", kpis)

        # Check KPI thresholds
        self._check_kpi_numeric("analyst", "structural_completeness", kpis["structural_completeness"])
        self._check_kpi_bool("analyst", "fact_check_pass", kpis["fact_check_pass"])
        self._check_kpi_numeric("analyst", "tech_stack_coverage", kpis["tech_stack_coverage"])

        logger.info(f"Analyst KPIs: {kpis}")
        return kpis

    # ---- Pipeline KPIs ----

    def track_pipeline_kpis(
        self,
        tti_seconds: float,
        success: bool,
        token_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Track Pipeline KPIs:
        - Time-to-Insight (TTI): ≤ 60s (shallow) / ≤ 120s (deep)
        - Task success rate: ≥ 98%
        - Token cost: ≤ ¥0.12 (Qwen) / ≤ $0.08 (GPT-4o)
        """
        kpis = {}

        # TTI scoring
        if tti_seconds <= 60:
            kpis["tti_score"] = 1.0  # Within shallow target
        elif tti_seconds <= 120:
            kpis["tti_score"] = 0.8  # Within deep target
        elif tti_seconds <= 180:
            kpis["tti_score"] = 0.5  # Acceptable
        else:
            kpis["tti_score"] = 0.2  # Too slow

        kpis["tti_seconds"] = tti_seconds

        # Success rate
        kpis["task_success"] = 1.0 if success else 0.0

        # Token cost estimate (rough: ~3 tokens per ¥0.001 for Qwen)
        if token_count:
            # Qwen: ~¥0.02/1K tokens → ¥0.12 budget ≈ 6000 tokens
            estimated_cost = token_count / 6000.0 * 0.12
            kpis["token_cost_ratio"] = min(estimated_cost / 0.12, 1.0) if estimated_cost > 0 else 1.0
            kpis["token_count"] = token_count

        self._persist("pipeline", kpis)

        # Check KPI thresholds
        self._check_kpi_numeric("pipeline", "tti_score", kpis["tti_score"])
        self._check_kpi_bool("pipeline", "task_success", success)

        logger.info(f"Pipeline KPIs: tti={tti_seconds:.1f}s, success={success}")
        return kpis

    # ---- Persistence ----

    def _check_kpi_numeric(self, agent: str, kpi_name: str, value: float) -> None:
        """Check a numeric KPI against its threshold, fire alert if violated."""
        try:
            self.alert_manager.check_kpi(agent, kpi_name, value)
        except Exception as e:
            logger.warning(f"KPI alert check failed: {e}")

    def _check_kpi_bool(self, agent: str, kpi_name: str, value: bool) -> None:
        """Check a boolean KPI against its threshold (True → 1.0, False → 0.0)."""
        self._check_kpi_numeric(agent, kpi_name, 1.0 if value else 0.0)

    def _persist(self, agent: str, kpis: Dict[str, Any]) -> None:
        """Append KPI record to JSONL metrics file."""
        try:
            self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "run_id": self._run_id,
                "agent": agent,
                "kpis": kpis,
                "timestamp": time.time(),
            }
            with open(self.metrics_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist KPIs: {e}")


# ---- Module-level singleton ----

_global_kpi_tracker: Optional[KPITracker] = None


def get_kpi_tracker(config: Optional[ConfigManager] = None) -> KPITracker:
    """Get or create the global KPI tracker singleton."""
    global _global_kpi_tracker
    if _global_kpi_tracker is None:
        _global_kpi_tracker = KPITracker(config=config)
    return _global_kpi_tracker
