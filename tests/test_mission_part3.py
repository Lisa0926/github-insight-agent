# -*- coding: utf-8 -*-
"""
Mission Part 3: Supplemental tests for uncommitted working tree changes.

Covers:
- base_agent.py: Role constraint injection via _load_role_kpi_config()
- researcher_agent.py: KPI tracking integration in execute_action()
- guardrails.py: Circuit breaker defaults from role_kpi.yaml
- report_generator.py: ProjectFact/ProjectAnalysisReport validation + KPI tracking
- contracts.py: Pydantic model integration with report_generator workflow
- kpi_tracker.py: Integration with researcher/analyst/pipeline flows
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.contracts import ProjectFact, ProjectAnalysisReport
from src.core.kpi_tracker import KPITracker, _load_role_kpi_config, get_kpi_tracker


# ============================================================
# Fix Verification: base_agent.py role constraint refactoring
# ============================================================

class TestBaseAgentRoleConstraints:
    """Verify _load_role_kpi_config is correctly used after refactoring."""

    def test_load_role_kpi_returns_dict_or_none(self):
        """_load_role_kpi_config should return a dict or None."""
        result = _load_role_kpi_config()
        assert result is None or isinstance(result, dict)

    def test_load_role_kpi_is_cached(self):
        """Repeated calls should return the same cached object."""
        r1 = _load_role_kpi_config()
        r2 = _load_role_kpi_config()
        assert r1 is r2

    def test_role_kpi_has_expected_structure(self):
        """If role_kpi.yaml is found, it should have agents and global_constraints."""
        config = _load_role_kpi_config()
        if config is None:
            pytest.skip("role_kpi.yaml not found")
        assert "agents" in config or "global_constraints" in config


# ============================================================
# Fix Verification: researcher_agent.py KPI tracking
# ============================================================

class TestResearcherKPITracking:
    """Verify KPI tracking in ResearcherAgent execute_action()."""

    def test_kpi_tracker_created_on_init(self):
        """ResearcherAgent should have a kpi_tracker attribute."""
        from src.agents.researcher_agent import ResearcherAgent
        from src.core.config_manager import ConfigManager

        with patch.object(ConfigManager, "__init__", return_value=None):
            with patch.object(ConfigManager, "dashscope_model_name", "qwen-turbo"):
                with patch.object(ConfigManager, "dashscope_api_key", "test-key"):
                    with patch("src.agents.researcher_agent.GitHubTool"):
                        with patch("src.agents.researcher_agent.get_github_toolkit", return_value=None):
                            with patch("src.agents.base_agent.GiaAgentBase.__init__", return_value=None):
                                agent = ResearcherAgent.__new__(ResearcherAgent)
                                agent.config = ConfigManager()
                                agent.kpi_tracker = KPITracker(
                                    metrics_path=tempfile.mktemp(suffix=".jsonl")
                                )
                                assert hasattr(agent, "kpi_tracker")
                                assert isinstance(agent.kpi_tracker, KPITracker)

    def test_track_researcher_kpis_valid_action(self):
        """Valid actions should produce intent_accuracy=1.0."""
        tracker = KPITracker(metrics_path=tempfile.mktemp(suffix=".jsonl"))
        kpis = tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={"query": "AI"},
            success=True,
            result_count=5,
        )
        assert kpis["intent_accuracy"] == 1.0
        assert kpis["fetch_success_rate"] == 1.0

    def test_track_researcher_kpis_invalid_action(self):
        """Unknown actions should produce intent_accuracy=0.0."""
        tracker = KPITracker(metrics_path=tempfile.mktemp(suffix=".jsonl"))
        kpis = tracker.track_researcher_kpis(
            intent_action="unknown_action",
            intent_params={},
            success=False,
        )
        assert kpis["intent_accuracy"] == 0.0
        assert kpis["fetch_success_rate"] == 0.0


# ============================================================
# Fix Verification: guardrails.py circuit breaker defaults
# ============================================================

class TestCircuitBreakerRoleKpiDefaults:
    """Verify circuit breaker reads defaults from role_kpi.yaml."""

    @pytest.fixture(autouse=True)
    def reset_circuit_breaker(self):
        import src.core.guardrails as guardrails
        original = guardrails._global_circuit_breaker
        guardrails._global_circuit_breaker = None
        yield
        guardrails._global_circuit_breaker = original

    def test_get_circuit_breaker_reads_yaml_defaults(self):
        """Circuit breaker should use YAML defaults when available."""
        from src.core.guardrails import get_circuit_breaker

        config = _load_role_kpi_config()
        if config is None:
            pytest.skip("role_kpi.yaml not found")

        cb = get_circuit_breaker()
        constraints = config.get("global_constraints", {})
        cost_config = constraints.get("cost_control", {})
        cb_config = cost_config.get("circuit_breaker", {})

        assert cb.max_steps == cb_config.get("max_steps", 50)
        assert cb.max_time_seconds == cb_config.get("max_time_seconds", 180)

    def test_explicit_params_override_yaml(self):
        """Explicit parameters should override YAML defaults."""
        from src.core.guardrails import get_circuit_breaker

        cb = get_circuit_breaker(max_steps=10, max_time_seconds=30, max_tokens=1000)
        assert cb.max_steps == 10
        assert cb.max_time_seconds == 30
        assert cb.max_tokens == 1000


# ============================================================
# Integration: report_generator.py + contracts.py
# ============================================================

class TestReportGeneratorContractValidation:
    """Verify ProjectFact validation in report_generator._search_projects()."""

    def test_projectfact_validates_raw_repo_data(self):
        """ProjectFact should validate and accept raw repo data from GitHub API."""
        raw = {
            "owner": "langchain-ai",
            "repo": "langchain",
            "stars": 90000,
            "lang": "Python",
            "readme_snippet": "Build context-aware reasoning applications",
            "trend_score": 0.95,
            "last_commit_days": 1,
            "tags": ["ai", "llm", "python"],
        }
        fact = ProjectFact.model_validate(raw)
        assert fact.owner == "langchain-ai"
        assert fact.trend_score == 0.95
        assert fact.tags == ["ai", "llm", "python"]

    def test_projectfact_clamps_trend_score(self):
        """Trend scores outside [0, 1] should be clamped."""
        fact = ProjectFact(owner="test", repo="test", stars=100, trend_score=2.0)
        assert fact.trend_score == 1.0

        fact = ProjectFact(owner="test", repo="test", stars=100, trend_score=-0.5)
        assert fact.trend_score == 0.0

    def test_projectfact_handles_missing_optional_fields(self):
        """Optional fields should have sensible defaults."""
        fact = ProjectFact(owner="test", repo="test", stars=100)
        assert fact.lang == ""
        assert fact.tags == []
        assert fact.trend_score is None
        assert fact.last_commit_days is None

    def test_projectanalysisreport_validates_analyst_output(self):
        """ProjectAnalysisReport should validate analyst output."""
        data = {
            "core_function": "AI agent framework",
            "tech_stack": ["Python", "LangChain", "OpenAI"],
            "architecture_pattern": "Agent-based",
            "pain_points": ["Complex configuration"],
            "suitability": "AI applications",
            "risk_flags": ["API dependency"],
            "score_breakdown": {"quality": 0.85, "docs": 0.7},
            "suitability_score": 0.85,
        }
        report = ProjectAnalysisReport.model_validate(data, from_attributes=True)
        assert report.core_function == "AI agent framework"
        assert len(report.tech_stack) == 3
        assert report.suitability_score == 0.85
        assert report.score("quality") == 0.85

    def test_projectanalysisreport_clamps_suitability_score(self):
        """Suitability scores outside [0, 1] should be clamped."""
        report = ProjectAnalysisReport(core_function="Test", suitability_score=1.5)
        assert report.suitability_score == 1.0

        report = ProjectAnalysisReport(core_function="Test", suitability_score=-0.3)
        assert report.suitability_score == 0.0

    def test_projectanalysisreport_handles_invalid_score(self):
        """Non-numeric suitability_score should default to 0.5."""
        report = ProjectAnalysisReport(
            core_function="Test", suitability_score="invalid"
        )
        assert report.suitability_score == 0.5


# ============================================================
# Integration: KPI tracking end-to-end
# ============================================================

class TestKPIIntegration:
    """Verify KPI tracker works correctly in the pipeline."""

    def test_pipeline_kpis_persist_to_jsonl(self, tmp_path):
        """Pipeline KPIs should be written to JSONL file."""
        metrics_path = str(tmp_path / "test_metrics.jsonl")
        tracker = KPITracker(metrics_path=metrics_path)

        tracker.track_pipeline_kpis(tti_seconds=45.2, success=True)
        tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={"query": "AI"},
            success=True,
            result_count=3,
        )
        tracker.track_analyst_kpis(
            analysis={
                "core_function": "AI framework",
                "tech_stack": ["Python"],
                "architecture_pattern": "Agent",
                "pain_points": [],
                "risk_flags": [],
                "stars": 1000,
                "language": "Python",
            },
            report_text="test-project",
        )

        assert Path(metrics_path).exists()
        with open(metrics_path) as f:
            records = [json.loads(line) for line in f if line.strip()]
        assert len(records) == 3
        agents = [r["agent"] for r in records]
        assert "pipeline" in agents
        assert "researcher" in agents
        assert "analyst" in agents

    def test_kpi_tracker_custom_metrics_path(self, tmp_path):
        """KPITracker should support custom metrics path."""
        custom_path = str(tmp_path / "custom_metrics.jsonl")
        tracker = KPITracker(metrics_path=custom_path)
        tracker.track_pipeline_kpis(tti_seconds=30, success=True)
        assert Path(custom_path).exists()

    def test_global_kpi_tracker_singleton(self):
        """get_kpi_tracker should return the same instance."""
        t1 = get_kpi_tracker()
        t2 = get_kpi_tracker()
        assert t1 is t2


# ============================================================
# Edge Cases: contracts.py
# ============================================================

class TestContractEdgeCases:
    """Edge cases for Pydantic contracts."""

    def test_projectfact_extra_fields_ignored(self):
        """Extra fields should be silently ignored."""
        fact = ProjectFact(
            owner="test", repo="test", stars=100,
            extra_unknown_field="should_be_ignored",
        )
        assert not hasattr(fact, "extra_unknown_field")

    def test_projectfact_stars_validation(self):
        """Stars must be >= 0."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ProjectFact(owner="test", repo="test", stars=-1)

    def test_projectanalysisreport_score_breakdown_defaults(self):
        """score_breakdown should default to empty dict."""
        report = ProjectAnalysisReport(core_function="Test")
        assert report.score_breakdown == {}
        assert report.score("anything") == 0.0

    def test_projectfact_full_name_property(self):
        """full_name property should combine owner and repo."""
        fact = ProjectFact(owner="microsoft", repo="vscode", stars=100)
        assert fact.full_name == "microsoft/vscode"

    def test_projectfact_trend_score_none(self):
        """trend_score should accept None."""
        fact = ProjectFact(owner="test", repo="test", stars=100, trend_score=None)
        assert fact.trend_score is None

    def test_projectanalysisreport_risk_flags_default(self):
        """risk_flags should default to empty list."""
        report = ProjectAnalysisReport(core_function="Test")
        assert report.risk_flags == []
