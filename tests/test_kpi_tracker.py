# -*- coding: utf-8 -*-
"""Tests for KPI tracker."""

import json
from pathlib import Path

import pytest

from src.core.kpi_tracker import KPITracker, _load_role_kpi_config, get_kpi_tracker


@pytest.fixture
def metrics_path(tmp_path):
    return str(tmp_path / "test_metrics.jsonl")


@pytest.fixture
def tracker(metrics_path):
    return KPITracker(metrics_path=metrics_path)


class TestKPITrackerInit:
    def test_default_metrics_path(self):
        tracker = KPITracker()
        assert tracker.metrics_path == Path.home() / ".hermes" / "gia_metrics.jsonl"

    def test_custom_metrics_path(self, metrics_path):
        tracker = KPITracker(metrics_path=metrics_path)
        assert str(tracker.metrics_path) == metrics_path

    def test_run_id_is_string(self, tracker):
        assert isinstance(tracker.run_id, str)

    def test_run_id_setter(self, tracker):
        tracker.run_id = "custom-123"
        assert tracker.run_id == "custom-123"


class TestResearcherKPIs:
    def test_valid_action(self, tracker):
        kpis = tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={"query": "AI"},
            success=True,
            result_count=5,
        )
        assert kpis["intent_accuracy"] == 1.0
        assert kpis["fetch_success_rate"] == 1.0
        assert kpis["rate_limit_handled"] is True

    def test_invalid_action(self, tracker):
        kpis = tracker.track_researcher_kpis(
            intent_action="unknown_action",
            intent_params={},
            success=False,
        )
        assert kpis["intent_accuracy"] == 0.0
        assert kpis["fetch_success_rate"] == 0.0

    def test_empty_result_not_error(self, tracker):
        kpis = tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={"query": "obscure"},
            success=True,
            result_count=0,
        )
        assert kpis["fetch_success_rate"] == 0.5

    def test_rate_limit_not_handled(self, tracker):
        kpis = tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={"query": "test"},
            success=False,
            api_429_count=3,
        )
        assert kpis["rate_limit_handled"] is False

    def test_rate_limit_handled_with_success(self, tracker):
        kpis = tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={"query": "test"},
            success=True,
            api_429_count=1,
        )
        assert kpis["rate_limit_handled"] is True


class TestAnalystKPIs:
    def test_structural_completeness_full(self, tracker):
        analysis = {
            "core_function": "Web framework",
            "tech_stack": ["Python", "FastAPI"],
            "architecture_pattern": "MVC",
            "pain_points": ["Complexity"],
            "risk_flags": ["Low maintainer count"],
            "stars": 1000,
            "language": "Python",
        }
        kpis = tracker.track_analyst_kpis(analysis=analysis, report_text="Test report")
        assert kpis["structural_completeness"] == 1.0
        assert kpis["fact_check_pass"] is True

    def test_structural_completeness_partial(self, tracker):
        analysis = {"core_function": "Web framework"}
        kpis = tracker.track_analyst_kpis(analysis=analysis, report_text="Test")
        assert kpis["structural_completeness"] == 0.2  # 1/5 fields

    def test_fact_check_fail_missing_data(self, tracker):
        analysis = {"core_function": "Test"}
        kpis = tracker.track_analyst_kpis(analysis=analysis, report_text="Test")
        assert kpis["fact_check_pass"] is False

    def test_tech_stack_coverage(self, tracker):
        analysis = {
            "core_function": "Test",
            "tech_stack": ["Python", "FastAPI"],
            "stars": 100,
            "language": "Python",
        }
        kpis = tracker.track_analyst_kpis(analysis=analysis, report_text="Test")
        assert kpis["tech_stack_coverage"] == pytest.approx(0.667, rel=0.01)


class TestPipelineKPIs:
    def test_tti_fast(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=30, success=True)
        assert kpis["tti_score"] == 1.0

    def test_tti_shallow_target(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=60, success=True)
        assert kpis["tti_score"] == 1.0

    def test_tti_deep_target(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=90, success=True)
        assert kpis["tti_score"] == 0.8

    def test_tti_acceptable(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=150, success=True)
        assert kpis["tti_score"] == 0.5

    def test_tti_too_slow(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=200, success=True)
        assert kpis["tti_score"] == 0.2

    def test_task_success(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=30, success=True)
        assert kpis["task_success"] == 1.0

    def test_task_failure(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=30, success=False)
        assert kpis["task_success"] == 0.0

    def test_token_cost_estimation(self, tracker):
        kpis = tracker.track_pipeline_kpis(tti_seconds=30, success=True, token_count=3000)
        assert kpis["token_count"] == 3000
        assert "token_cost_ratio" in kpis


class TestPersistence:
    def test_jsonl_persistence(self, tracker, metrics_path):
        tracker.track_pipeline_kpis(tti_seconds=30, success=True)
        assert Path(metrics_path).exists()

        with open(metrics_path, "r") as f:
            records = [json.loads(line) for line in f if line.strip()]
        assert len(records) == 1
        assert records[0]["agent"] == "pipeline"
        assert records[0]["run_id"] == tracker.run_id
        assert "timestamp" in records[0]

    def test_multiple_records(self, tracker, metrics_path):
        tracker.track_pipeline_kpis(tti_seconds=30, success=True)
        tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={},
            success=True,
        )

        with open(metrics_path, "r") as f:
            records = [json.loads(line) for line in f if line.strip()]
        assert len(records) == 2


class TestLoadRoleKpiConfig:
    def test_returns_dict_or_none(self):
        config = _load_role_kpi_config()
        # May be None if file not found, or a dict if found
        assert config is None or isinstance(config, dict)

    def test_caching(self):
        config1 = _load_role_kpi_config()
        config2 = _load_role_kpi_config()
        assert config1 is config2


class TestGetKpiTracker:
    def test_singleton(self):
        t1 = get_kpi_tracker()
        t2 = get_kpi_tracker()
        assert t1 is t2
