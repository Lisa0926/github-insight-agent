# -*- coding: utf-8 -*-
"""Mission Part 3 supplemental tests — May 8, 2026 (14:47 mission).

Covers the current uncommitted changes:
1. span_injector.py — new untracked module (SpanAttributeInjector)
2. analyst_agent._fallback_analysis — new structured fallback method
3. cli.app._check_studio_reachable — new helper function
4. base_agent._is_response_error — new error detection method
"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 1. SpanInjector — new untracked module
# ============================================================

class TestSpanInjectorModule:
    """Test src/core/span_injector.py module."""

    def test_import_span_injector(self):
        """Module should import without errors."""
        from src.core.span_injector import (
            SpanAttributeInjector,
            configure_span_injector,
            get_injected_run_id,
        )
        assert SpanAttributeInjector is not None
        assert configure_span_injector is not None
        assert get_injected_run_id is not None

    def test_injector_initialization(self):
        """SpanAttributeInjector should initialize with defaults."""
        from src.core.span_injector import SpanAttributeInjector
        inj = SpanAttributeInjector(run_id="test-run-123")
        assert inj.run_id == "test-run-123"
        assert inj.service_name == "GitHub Insight Agent"

    def test_injector_custom_service_name(self):
        """Should accept custom service name."""
        from src.core.span_injector import SpanAttributeInjector
        inj = SpanAttributeInjector(run_id="r1", service_name="Custom Service")
        assert inj.service_name == "Custom Service"

    def test_on_start_injects_all_attributes(self):
        """on_start should inject all expected span attributes."""
        from src.core.span_injector import SpanAttributeInjector
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        inj = SpanAttributeInjector(run_id="run-42", service_name="TestSvc")
        inj.on_start(mock_span)

        calls = [c.args for c in mock_span.set_attribute.call_args_list]
        assert ("gen_ai.conversation.id", "run-42") in calls
        assert ("service.name", "TestSvc") in calls
        assert ("project.run_id", "run-42") in calls
        assert ("project.service_name", "TestSvc") in calls

    def test_on_start_none_span_no_crash(self):
        """Should not crash on None span."""
        from src.core.span_injector import SpanAttributeInjector
        inj = SpanAttributeInjector(run_id="r1")
        inj.on_start(None)

    def test_on_start_non_recording_span(self):
        """Should not inject on non-recording spans."""
        from src.core.span_injector import SpanAttributeInjector
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        inj = SpanAttributeInjector(run_id="r1")
        inj.on_start(mock_span)
        mock_span.set_attribute.assert_not_called()

    def test_on_end_no_op(self):
        """on_end should be a no-op."""
        from src.core.span_injector import SpanAttributeInjector
        inj = SpanAttributeInjector(run_id="r1")
        inj.on_end(MagicMock())  # Should not raise

    def test_shutdown_no_op(self):
        """shutdown should be a no-op."""
        from src.core.span_injector import SpanAttributeInjector
        inj = SpanAttributeInjector(run_id="r1")
        inj.shutdown()  # Should not raise

    def test_force_flush_returns_true(self):
        """force_flush should return True."""
        from src.core.span_injector import SpanAttributeInjector
        inj = SpanAttributeInjector(run_id="r1")
        assert inj.force_flush() is True
        assert inj.force_flush(timeout_millis=1000) is True

    def test_configure_sets_module_level(self):
        """configure_span_injector should set module-level variables."""
        from src.core.span_injector import (
            configure_span_injector,
            get_injected_run_id,
        )
        with patch("opentelemetry.trace.get_tracer_provider") as mock_get:
            mock_get.return_value = MagicMock()  # Not a TracerProvider
            configure_span_injector("configured-run", "ConfiguredService")
            assert get_injected_run_id() == "configured-run"

    def test_configure_with_real_provider(self):
        """Should register processor when TracerProvider is available."""
        from src.core.span_injector import configure_span_injector
        from opentelemetry.sdk.trace import TracerProvider

        mock_provider = MagicMock(spec=TracerProvider)

        with patch("opentelemetry.trace.get_tracer_provider", return_value=mock_provider):
            configure_span_injector("real-run")
            mock_provider.add_span_processor.assert_called_once()

    def test_configure_graceful_degradation(self):
        """Should not crash if OTel is unavailable."""
        from src.core.span_injector import configure_span_injector
        with patch("opentelemetry.trace.get_tracer_provider", side_effect=ImportError):
            configure_span_injector("fail-run")  # Should not raise


# ============================================================
# 2. AnalystAgent._fallback_analysis
# ============================================================

class TestFallbackAnalysis:
    """Test analyst_agent._fallback_analysis for structured fallback."""

    def _make_agent(self):
        from src.agents.analyst_agent import AnalystAgent
        agent = AnalystAgent.__new__(AnalystAgent)
        return agent

    def test_fallback_basic_parsing(self):
        """Should parse project_info and return structured fallback."""
        agent = self._make_agent()
        project_info = (
            "- 项目名称：test/repo\n"
            "- 编程语言：Python\n"
            "- 简介：A test project"
        )
        result = agent._fallback_analysis(project_info)
        assert result["core_function"] == "A test project"
        assert result["tech_stack"]["language"] == "Python"
        assert result["maturity_assessment"] == "unknown"
        assert result["_llm_error"] is True
        assert result["suitability_score"] == 0.5

    def test_fallback_missing_fields(self):
        """Should handle project_info without expected fields."""
        agent = self._make_agent()
        result = agent._fallback_analysis("some random text")
        assert result["core_function"] == "Unable to determine (LLM analysis unavailable)"
        assert result["tech_stack"]["language"] == "Unknown"

    def test_fallback_empty_input(self):
        """Should handle empty project_info."""
        agent = self._make_agent()
        result = agent._fallback_analysis("")
        assert result["_llm_error"] is True
        assert result["suitability_score"] == 0.5

    def test_fallback_has_all_required_keys(self):
        """Should return all keys expected by AnalysisResult."""
        agent = self._make_agent()
        result = agent._fallback_analysis("- 项目名称：x/y\n- 编程语言：Go\n- 简介: test")
        required_keys = [
            "core_function", "tech_stack", "architecture_pattern",
            "pain_points_solved", "unique_value", "risk_flags",
            "suitability_score", "score_breakdown", "maturity_assessment",
            "recommendation", "competitive_analysis", "_llm_error",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"


# ============================================================
# 3. base_agent._is_response_error
# ============================================================

class TestResponseErrorDetection:
    """Test base_agent._is_response_error for API error detection."""

    def _make_agent(self):
        from src.agents.base_agent import GiaAgentBase
        agent = GiaAgentBase.__new__(GiaAgentBase)
        return agent

    def test_detects_metadata_error(self):
        """Should detect error in metadata."""
        agent = self._make_agent()
        response = {"content": "", "metadata": {"error": "rate limited"}}
        assert agent._is_response_error(response) is True

    def test_detects_error_prefix(self):
        """Should detect DashScope API error prefix."""
        agent = self._make_agent()
        response = {"content": "DashScope API error: timeout", "metadata": {}}
        assert agent._is_response_error(response) is True

    def test_normal_response_not_error(self):
        """Normal response should not be flagged as error."""
        agent = self._make_agent()
        response = {"content": "Hello world", "metadata": {}}
        assert agent._is_response_error(response) is False

    def test_empty_metadata_not_error(self):
        """Empty metadata should not be error."""
        agent = self._make_agent()
        response = {"content": "OK", "metadata": None}
        assert agent._is_response_error(response) is False

    def test_non_dict_response_not_error(self):
        """Non-dict response should not be flagged."""
        agent = self._make_agent()
        assert agent._is_response_error("plain string") is False
        assert agent._is_response_error(None) is False


# ============================================================
# 4. cli.app._check_studio_reachable
# ============================================================

class TestCheckStudioReachable:
    """Test _check_studio_reachable helper function."""

    def test_studio_reachable_returns_true(self):
        """Should return True when studio responds with 200."""
        from src.cli.app import _check_studio_reachable
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            assert _check_studio_reachable("http://studio:3000") is True

    def test_studio_unreachable_returns_false(self):
        """Should return False on connection error."""
        from src.cli.app import _check_studio_reachable
        with patch("requests.get", side_effect=ConnectionError):
            assert _check_studio_reachable("http://studio:3000") is False

    def test_studio_non_200_returns_false(self):
        """Should return False on non-200 status."""
        from src.cli.app import _check_studio_reachable
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_get.return_value = mock_resp
            assert _check_studio_reachable("http://studio:3000") is False

    def test_studio_timeout_returns_false(self):
        """Should return False on timeout."""
        from src.cli.app import _check_studio_reachable
        with patch("requests.get", side_effect=TimeoutError):
            assert _check_studio_reachable("http://studio:3000") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
