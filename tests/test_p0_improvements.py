# -*- coding: utf-8 -*-
"""Tests for P0 improvements: ReportGenerator System Prompt + KPI Alert Manager."""

import pytest

from src.core.kpi_tracker import (
    KPIAlert,
    KPIAlertLevel,
    KPIAlertManager,
    KPITracker,
    get_alert_manager,
)


# ============================================================
# P0-1: ReportGenerator System Prompt
# ============================================================

class TestReportGeneratorSystemPrompt:
    """Test that ReportGenerator has LLM-driven System Prompt"""

    def test_system_prompt_loaded_from_yaml(self):
        from src.workflows.report_generator import ReportGenerator
        prompt = ReportGenerator._build_system_prompt()
        assert len(prompt) > 100

    def test_system_prompt_defines_role(self):
        from src.workflows.report_generator import ReportGenerator
        prompt = ReportGenerator._build_system_prompt()
        assert "报告编排" in prompt or "编排者" in prompt or "交付" in prompt

    def test_system_prompt_defines_constraints(self):
        from src.workflows.report_generator import ReportGenerator
        prompt = ReportGenerator._build_system_prompt()
        assert "不编造" in prompt or "约束" in prompt

    def test_system_prompt_defines_tone(self):
        from src.workflows.report_generator import ReportGenerator
        prompt = ReportGenerator._build_system_prompt()
        assert "数据驱动" in prompt or "严谨" in prompt

    def test_followup_system_prompt_exists(self):
        from src.workflows.report_generator import ReportGenerator
        prompt = ReportGenerator._build_system_prompt("followup_system_prompt")
        assert len(prompt) > 50

    def test_followup_prompt_references_context(self):
        from src.workflows.report_generator import ReportGenerator
        prompt = ReportGenerator._build_system_prompt("followup_system_prompt")
        assert "上下文" in prompt or "context" in prompt


# ============================================================
# P0-2: KPI Alert Manager
# ============================================================

class TestKPIAlertManagerBasic:
    """Test KPIAlertManager threshold checking"""

    def _make_manager(self):
        return KPIAlertManager()

    def test_check_passing_kpi_returns_none(self):
        mgr = self._make_manager()
        # intent_accuracy threshold is 0.95, passing 1.0 should not violate
        alert = mgr.check_kpi("researcher", "intent_accuracy", 1.0)
        assert alert is None

    def test_check_failing_kpi_returns_alert(self):
        mgr = self._make_manager()
        # intent_accuracy threshold is 0.95, passing 0.0 should violate
        alert = mgr.check_kpi("researcher", "intent_accuracy", 0.0)
        assert alert is not None
        assert alert.agent == "researcher"
        assert alert.kpi_name == "intent_accuracy"
        assert alert.actual_value == 0.0

    def test_alert_severity_levels(self):
        mgr = self._make_manager()
        # fetch_success_rate has severity="critical" with min=0.98
        alert = mgr.check_kpi("researcher", "fetch_success_rate", 0.5)
        assert alert is not None
        assert alert.severity == KPIAlertLevel.CRITICAL

    def test_violations_list(self):
        mgr = self._make_manager()
        mgr.check_kpi("researcher", "intent_accuracy", 0.0)
        mgr.check_kpi("researcher", "fetch_success_rate", 0.0)
        assert len(mgr.violations) == 2

    def test_reset_clears_violations(self):
        mgr = self._make_manager()
        mgr.check_kpi("researcher", "intent_accuracy", 0.0)
        assert len(mgr.violations) == 1
        mgr.reset()
        assert len(mgr.violations) == 0

    def test_summary(self):
        mgr = self._make_manager()
        mgr.check_kpi("researcher", "intent_accuracy", 0.0)
        mgr.check_kpi("pipeline", "task_success", 0.0)
        summary = mgr.get_summary()
        assert summary["total_violations"] == 2
        assert "researcher" in summary["violations_by_agent"]
        assert "pipeline" in summary["violations_by_agent"]

    def test_unknown_agent_no_alert(self):
        mgr = self._make_manager()
        alert = mgr.check_kpi("unknown_agent", "some_metric", 0.0)
        assert alert is None

    def test_unknown_kpi_no_alert(self):
        mgr = self._make_manager()
        alert = mgr.check_kpi("researcher", "nonexistent_kpi", 0.0)
        assert alert is None


class TestKPIAlertManagerCallbacks:
    """Test callback registration and invocation"""

    def test_callback_invoked_on_warning(self):
        mgr = KPIAlertManager()
        callback_calls = []

        def on_alert(alert):
            callback_calls.append(alert)

        mgr.register_callback(on_alert)
        # intent_accuracy has severity="warning", min=0.95
        mgr.check_kpi("researcher", "intent_accuracy", 0.5)
        assert len(callback_calls) == 1

    def test_callback_invoked_on_critical(self):
        mgr = KPIAlertManager()
        callback_calls = []

        def on_alert(alert):
            callback_calls.append(alert)

        mgr.register_callback(on_alert)
        # fetch_success_rate has severity="critical", min=0.98
        mgr.check_kpi("researcher", "fetch_success_rate", 0.5)
        assert len(callback_calls) == 1

    def test_callback_not_invoked_on_info(self):
        mgr = KPIAlertManager()
        callback_calls = []

        def on_alert(alert):
            callback_calls.append(alert)

        mgr.register_callback(on_alert)
        # tech_stack_coverage has severity="info", min=0.67
        mgr.check_kpi("analyst", "tech_stack_coverage", 0.0)
        assert len(callback_calls) == 0

    def test_callback_failure_does_not_crash(self):
        mgr = KPIAlertManager()

        def bad_callback(alert):
            raise RuntimeError("callback error")

        mgr.register_callback(bad_callback)
        # Should not raise
        mgr.check_kpi("researcher", "intent_accuracy", 0.0)


class TestKPIAlertManagerThresholdParsing:
    """Test target string parsing from role_kpi.yaml"""

    def test_parse_pct_target(self):
        mgr = KPIAlertManager()
        result = mgr._parse_target("≥ 95%")
        assert result is not None
        assert result["min"] == pytest.approx(0.95)

    def test_parse_pct_with_equals(self):
        mgr = KPIAlertManager()
        result = mgr._parse_target(">= 98%")
        assert result is not None
        assert result["min"] == pytest.approx(0.98)

    def test_parse_time_target(self):
        mgr = KPIAlertManager()
        result = mgr._parse_target("≤ 60s")
        assert result is not None
        assert result["max"] == pytest.approx(60.0)

    def test_parse_ratio_target(self):
        mgr = KPIAlertManager()
        result = mgr._parse_target("≥ 4.5 / 5.0")
        assert result is not None
        assert result["min"] == pytest.approx(0.9)

    def test_parse_upper_bound(self):
        mgr = KPIAlertManager()
        result = mgr._parse_target("≤ 0.12")
        assert result is not None
        assert result["max"] == pytest.approx(0.12)

    def test_parse_unrecognized_returns_none(self):
        mgr = KPIAlertManager()
        result = mgr._parse_target("something weird")
        assert result is None


class TestKPIAlertManagerIntegration:
    """Test alert manager integration with KPITracker"""

    @pytest.fixture
    def tracker_with_alerts(self, tmp_path):
        alert_mgr = KPIAlertManager()
        return KPITracker(metrics_path=str(tmp_path / "test.jsonl"), alert_manager=alert_mgr), alert_mgr

    def test_track_researcher_fires_alert_on_failure(self, tracker_with_alerts):
        tracker, alert_mgr = tracker_with_alerts
        # Invalid action should trigger intent_accuracy = 0.0 (violates min=0.95)
        tracker.track_researcher_kpis(
            intent_action="unknown_action",
            intent_params={},
            success=False,
        )
        assert len(alert_mgr.violations) >= 1

    def test_track_pipeline_fires_alert_on_slow_tti(self, tracker_with_alerts):
        tracker, alert_mgr = tracker_with_alerts
        # tti_score=0.2 (too slow) should violate tti_score min=0.5
        tracker.track_pipeline_kpis(tti_seconds=200, success=True)
        assert len(alert_mgr.violations) >= 1

    def test_track_pipeline_fires_alert_on_failure(self, tracker_with_alerts):
        tracker, alert_mgr = tracker_with_alerts
        # task_success=0.0 should violate task_success min=1.0
        tracker.track_pipeline_kpis(tti_seconds=30, success=False)
        assert len(alert_mgr.violations) >= 1

    def test_track_researcher_no_alert_on_success(self, tracker_with_alerts):
        tracker, alert_mgr = tracker_with_alerts
        # All passing KPIs should not fire alerts
        tracker.track_researcher_kpis(
            intent_action="search_repositories",
            intent_params={"query": "test"},
            success=True,
            result_count=5,
        )
        assert len(alert_mgr.violations) == 0


class TestGetAlertManager:
    def test_singleton(self):
        m1 = get_alert_manager()
        m2 = get_alert_manager()
        assert m1 is m2

    def test_reset(self):
        mgr = get_alert_manager()
        mgr.check_kpi("researcher", "intent_accuracy", 0.0)
        assert len(mgr.violations) >= 1
        mgr.reset()
        assert len(mgr.violations) == 0
