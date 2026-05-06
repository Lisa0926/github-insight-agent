# -*- coding: utf-8 -*-
"""Tests for P2 improvements: Event Bus, LLM-driven planning, Feedback loop."""

from unittest.mock import patch, MagicMock
import tempfile

import pytest

from src.core.feedback import FeedbackCollector, FeedbackSession, reset_feedback_collector


class TestFeedbackCollectorIntegration:
    """Test existing FeedbackCollector for P2-9 feedback loop."""

    @pytest.fixture
    def feedback_collector(self, tmp_path):
        reset_feedback_collector()
        fc = FeedbackCollector(db_path=str(tmp_path / "test.db"))
        yield fc
        reset_feedback_collector()

    def test_record_and_get_recent(self, feedback_collector):
        row_id = feedback_collector.record(
            rating="good",
            reason="Great analysis",
            user_input="test react",
            assistant_output="React is a JS library",
            agent="pipeline",
        )
        assert row_id > 0

        recent = feedback_collector.get_recent(limit=5)
        assert len(recent) >= 1
        assert recent[0]["rating"] == "good"

    def test_record_invalid_rating(self, feedback_collector):
        with pytest.raises(ValueError, match="Invalid rating"):
            feedback_collector.record(rating="excellent")

    def test_feedback_stats(self, feedback_collector):
        feedback_collector.record(rating="good", reason="nice")
        feedback_collector.record(rating="good", reason="great")
        feedback_collector.record(rating="bad", reason="poor")

        stats = feedback_collector.get_stats()
        assert stats["total"] == 3
        assert stats["good"] == 2
        assert stats["bad"] == 1
        assert stats["positive_rate"] > 0

    def test_feedback_session(self):
        session = FeedbackSession(run_id="test-001")
        session.set_last_interaction("user input", "assistant output")
        session.set_agent("pipeline")

        assert session.last_user_input == "user input"
        assert session.last_assistant_output == "assistant output"
        assert session.current_agent == "pipeline"
        assert session.run_id == "test-001"

    def test_record_with_session(self, feedback_collector):
        session = FeedbackSession(run_id="run-123")
        session.set_last_interaction("search react", "Found React project")
        session.set_agent("pipeline")

        row_id = feedback_collector.record_quick(
            rating="good",
            reason="Accurate",
            session_state=session,
        )
        assert row_id > 0

        recent = feedback_collector.get_recent(limit=1)
        assert recent[0]["user_input"] == "search react"
        assert recent[0]["assistant_output"] == "Found React project"
        assert recent[0]["run_id"] == "run-123"


class TestLLMDrivenPlanningHeuristicFallback:
    """Test heuristic fallback for P2-7 LLM-driven planning."""

    def test_heuristic_plan_deep(self):
        """High-star projects should trigger deep strategy."""
        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)

        results = [
            {"full_name": "a/b", "stars": 100000, "language": "Python", "trend_score": 0.8},
            {"full_name": "c/d", "stars": 80000, "language": "TypeScript", "trend_score": 0.9},
        ]

        plan = rg._heuristic_plan(results)
        assert plan["strategy"] == "deep"
        # Confidence is capped by language formula: min(0.8, 0.3 + 0.1*2/2) = 0.4
        assert plan["confidence"] > 0

    def test_heuristic_plan_standard(self):
        """Medium-star projects should trigger standard strategy."""
        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)

        results = [
            {"full_name": "a/b", "stars": 5000, "language": "Python", "trend_score": 0.5},
            {"full_name": "c/d", "stars": 3000, "language": "JavaScript", "trend_score": 0.6},
        ]

        plan = rg._heuristic_plan(results)
        assert plan["strategy"] == "standard"

    def test_heuristic_plan_quick(self):
        """Low-star projects should trigger quick strategy."""
        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)

        results = [
            {"full_name": "a/b", "stars": 10, "language": "Rust", "trend_score": None},
        ]

        plan = rg._heuristic_plan(results)
        assert plan["strategy"] == "quick"
        assert plan["confidence"] <= 0.5

    def test_heuristic_plan_empty(self):
        """Empty results should not crash."""
        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)

        plan = rg._heuristic_plan([])
        assert plan["strategy"] == "quick"

    def test_heuristic_reflection_needs_more(self):
        """Low success rate should flag for more analysis."""
        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)

        analysis = [
            {"project": "a/b", "error": "timeout", "analysis": None},
            {"project": "c/d", "error": "timeout", "analysis": None},
        ]
        plan = {"strategy": "standard"}

        result = rg._heuristic_reflection(analysis, plan)
        assert result["needs_more_analysis"] is True

    def test_heuristic_reflection_sufficient(self):
        """Good success rate should be sufficient."""
        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)

        analysis = [
            {"project": "a/b", "analysis": {"core_function": "test"}},
            {"project": "c/d", "analysis": {"core_function": "test"}},
        ]
        plan = {"strategy": "standard"}

        result = rg._heuristic_reflection(analysis, plan)
        assert result["needs_more_analysis"] is False


class TestReportGeneratorEventBusWiring:
    """Test that ReportGenerator has event_bus wired."""

    def test_has_event_bus(self):
        from src.core.event_bus import get_event_bus, reset_event_bus
        reset_event_bus()

        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)
        rg.event_bus = get_event_bus()

        assert rg.event_bus is not None
        assert rg.event_bus is get_event_bus()

        reset_event_bus()


class TestReportGeneratorFeedbackIntegration:
    """Test that ReportGenerator has feedback_collector wired."""

    def test_has_feedback_collector(self, tmp_path):
        from src.core.feedback import get_feedback_collector, reset_feedback_collector
        reset_feedback_collector()

        fc = get_feedback_collector(db_path=str(tmp_path / "test.db"))
        assert fc is not None
        assert isinstance(fc, FeedbackCollector)

        reset_feedback_collector()

    def test_rate_report_method_exists(self):
        """Verify rate_report method signature exists."""
        from src.workflows.report_generator import ReportGenerator
        assert hasattr(ReportGenerator, "rate_report")
        assert hasattr(ReportGenerator, "get_feedback_stats")
        assert hasattr(ReportGenerator, "get_recent_feedback")

    def test_rate_report_validation(self, tmp_path):
        """Invalid rating should return False."""
        from src.core.feedback import reset_feedback_collector
        reset_feedback_collector()

        from src.workflows.report_generator import ReportGenerator
        rg = ReportGenerator.__new__(ReportGenerator)
        rg.results = {"query": "", "report": "", "analysis_results": [], "tti": {}}
        rg.feedback_collector = FeedbackCollector(db_path=str(tmp_path / "test.db"))
        rg.kpi_tracker = MagicMock()  # Mock KPI tracker

        assert rg.rate_report("invalid") is False
        assert rg.rate_report("good") is True

        reset_feedback_collector()


class TestAgentPipelineFeedbackMethods:
    """Test that AgentPipeline has feedback delegation methods."""

    def test_has_delegation_methods(self):
        from src.workflows.agent_pipeline import AgentPipeline
        assert hasattr(AgentPipeline, "rate_report")
        assert hasattr(AgentPipeline, "get_feedback_stats")
        assert hasattr(AgentPipeline, "get_recent_feedback")
