# -*- coding: utf-8 -*-
"""
Tracing tests — OpenTelemetry tracing via AgentScope

Tests that:
1. @trace decorator passes through correctly when tracing is disabled
2. Fallback trace decorator works when agentscope.tracing is unavailable
3. Tracing configuration is correctly wired in CLI app
4. Key agent methods have @trace applied
5. Tracing spans contain expected attributes when enabled
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ============================================================
# 1. @trace Decorator Passthrough (tracing disabled)
# ============================================================

class TestTraceDecoratorPassthrough:
    """When tracing is disabled, @trace should be a no-op"""

    def test_sync_function_traced(self):
        """Synchronous functions should work with @trace when disabled"""
        from agentscope.tracing import trace

        @trace(name="test.sync_func")
        def add(a: int, b: int) -> int:
            return a + b

        result = add(3, 4)
        assert result == 7

    def test_async_function_traced(self):
        """Async functions should work with @trace when disabled"""
        import asyncio
        from agentscope.tracing import trace

        @trace(name="test.async_func")
        async def greet(name: str) -> str:
            return f"Hello, {name}"

        result = asyncio.run(greet("World"))
        assert result == "Hello, World"

    def test_method_traced(self):
        """Class methods should work with @trace"""
        from agentscope.tracing import trace

        class MyAgent:
            @trace(name="agent.process")
            def process(self, data: str) -> str:
                return data.upper()

        agent = MyAgent()
        assert agent.process("hello") == "HELLO"

    def test_generator_traced(self):
        """Generator functions should work with @trace"""
        from agentscope.tracing import trace

        @trace(name="test.generator")
        def gen_items(n: int):
            for i in range(n):
                yield i

        items = list(gen_items(3))
        assert items == [0, 1, 2]

    def test_exception_passthrough(self):
        """Exceptions should propagate through @trace"""
        from agentscope.tracing import trace

        @trace(name="test.error")
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_func()


# ============================================================
# 2. Fallback Trace Decorator
# ============================================================

class TestFallbackTraceDecorator:
    """Test that fallback trace decorators work in each module"""

    def test_researcher_agent_trace_available(self):
        """ResearcherAgent should have trace (real or fallback)"""
        from src.agents.researcher_agent import trace

        @trace(name="test.fallback")
        def dummy() -> int:
            return 42

        assert dummy() == 42

    def test_analyst_agent_trace_available(self):
        """AnalystAgent should have trace (real or fallback)"""
        from src.agents.analyst_agent import trace

        @trace(name="test.fallback")
        def dummy() -> int:
            return 42

        assert dummy() == 42

    def test_github_tool_trace_available(self):
        """GitHubTool should have trace (real or fallback)"""
        from src.tools.github_tool import trace

        @trace(name="test.fallback")
        def dummy() -> int:
            return 42

        assert dummy() == 42

    def test_report_generator_trace_available(self):
        """ReportGenerator should have trace (real or fallback)"""
        from src.workflows.report_generator import trace

        @trace(name="test.fallback")
        def dummy() -> int:
            return 42

        assert dummy() == 42

    def test_model_wrapper_trace_available(self):
        """Model wrapper should have trace (real or fallback)"""
        from src.core.dashscope_wrapper import trace

        @trace(name="test.fallback")
        def dummy() -> int:
            return 42

        assert dummy() == 42

    def test_agent_pipeline_trace_available(self):
        """AgentPipeline should have trace (real or fallback)"""
        from src.workflows.agent_pipeline import trace

        @trace(name="test.fallback")
        def dummy() -> int:
            return 42

        assert dummy() == 42


# ============================================================
# 3. Tracing Configuration
# ============================================================

class TestTracingConfiguration:
    """Test tracing setup functions in CLI app"""

    def test_setup_studio_passes_tracing_url(self):
        """_setup_studio should pass tracing_url when enabled"""
        from src.cli.app import _setup_studio
        import agentscope

        mock_config = MagicMock()
        mock_config.agentscope_studio_url = "http://studio:3000"
        mock_config.agentscope_run_name = "test_run"
        mock_config.agentscope_enable_tracing = True
        mock_config.agentscope_tracing_url = "http://otel:4318"

        with patch.object(agentscope, "init") as mock_init, \
             patch("src.agents.researcher_agent.set_studio_config"), \
             patch("src.agents.analyst_agent.set_studio_config"):

            _setup_studio(mock_config)

            call_kwargs = mock_init.call_args.kwargs
            assert call_kwargs.get("studio_url") == "http://studio:3000"
            assert call_kwargs.get("tracing_url") == "http://otel:4318"

    def test_setup_studio_always_enables_tracing(self):
        """_setup_studio should always enable tracing to Studio's OTLP endpoint"""
        from src.cli.app import _setup_studio
        import agentscope

        mock_config = MagicMock()
        mock_config.agentscope_studio_url = "http://studio:3000"
        mock_config.agentscope_run_name = "test_run"
        mock_config.agentscope_enable_tracing = False
        mock_config.agentscope_tracing_url = ""

        with patch.object(agentscope, "init") as mock_init, \
             patch("src.agents.researcher_agent.set_studio_config"), \
             patch("src.agents.analyst_agent.set_studio_config"):

            _setup_studio(mock_config)

            call_kwargs = mock_init.call_args.kwargs
            assert call_kwargs.get("studio_url") == "http://studio:3000"
            # tracing_url should include /v1/traces suffix for OTLP endpoint
            assert call_kwargs.get("tracing_url") == "http://studio:3000/v1/traces"

    def test_setup_tracing_standalone(self):
        """_setup_tracing should call agentscope.init with tracing_url only"""
        from src.cli.app import _setup_tracing
        import agentscope

        mock_config = MagicMock()
        mock_config.agentscope_tracing_url = "http://otel:4318"

        with patch.object(agentscope, "init") as mock_init:
            _setup_tracing(mock_config)

            call_kwargs = mock_init.call_args.kwargs
            assert call_kwargs.get("tracing_url") == "http://otel:4318"

    def test_setup_tracing_no_url_skips(self):
        """_setup_tracing should skip when no URL is provided"""
        from src.cli.app import _setup_tracing
        import agentscope

        mock_config = MagicMock()
        mock_config.agentscope_tracing_url = ""

        with patch.object(agentscope, "init") as mock_init:
            _setup_tracing(mock_config)
            mock_init.assert_not_called()


# ============================================================
# 4. Traced Methods Have Decorator Applied
# ============================================================

class TestTracedMethods:
    """Verify @trace decorator is applied to key methods"""

    def test_researcher_reply_traced(self):
        """ResearcherAgent.reply should have @trace wrapper"""
        from src.agents.researcher_agent import ResearcherAgent

        # Wrapped function should have __wrapped__ attribute
        reply = ResearcherAgent.reply
        assert hasattr(reply, "__wrapped__"), "reply() should be wrapped by @trace"

    def test_researcher_understand_intent_traced(self):
        """ResearcherAgent._understand_intent should have @trace wrapper"""
        from src.agents.researcher_agent import ResearcherAgent

        method = ResearcherAgent._understand_intent
        assert hasattr(method, "__wrapped__")

    def test_researcher_call_llm_traced(self):
        """ResearcherAgent._call_llm should have @trace wrapper"""
        from src.agents.researcher_agent import ResearcherAgent

        method = ResearcherAgent._call_llm
        assert hasattr(method, "__wrapped__")

    def test_researcher_search_and_analyze_traced(self):
        """ResearcherAgent.search_and_analyze should have @trace wrapper"""
        from src.agents.researcher_agent import ResearcherAgent

        method = ResearcherAgent.search_and_analyze
        assert hasattr(method, "__wrapped__")

    def test_analyst_reply_traced(self):
        """AnalystAgent.reply should have @trace wrapper"""
        from src.agents.analyst_agent import AnalystAgent

        method = AnalystAgent.reply
        assert hasattr(method, "__wrapped__")

    def test_analyst_analyze_with_llm_traced(self):
        """AnalystAgent._analyze_with_llm should have @trace wrapper"""
        from src.agents.analyst_agent import AnalystAgent

        method = AnalystAgent._analyze_with_llm
        assert hasattr(method, "__wrapped__")

    def test_dashscope_wrapper_traced(self):
        """DashScopeWrapper.__call__ should have @trace wrapper"""
        from src.core.dashscope_wrapper import DashScopeWrapper

        method = DashScopeWrapper.__call__
        assert hasattr(method, "__wrapped__")

    def test_github_tool_methods_traced(self):
        """GitHubTool methods should have @trace wrapper"""
        from src.tools.github_tool import GitHubTool

        assert hasattr(GitHubTool.search_repositories, "__wrapped__")
        assert hasattr(GitHubTool.get_readme, "__wrapped__")
        assert hasattr(GitHubTool.get_repo_info, "__wrapped__")

    def test_report_generator_methods_traced(self):
        """ReportGenerator methods should have @trace wrapper"""
        from src.workflows.report_generator import ReportGenerator

        assert hasattr(ReportGenerator.execute, "__wrapped__")
        assert hasattr(ReportGenerator._generate_report, "__wrapped__")
        assert hasattr(ReportGenerator.handle_followup, "__wrapped__")

    def test_agent_pipeline_methods_traced(self):
        """AgentPipeline methods should have @trace wrapper"""
        from src.workflows.agent_pipeline import AgentPipeline

        assert hasattr(AgentPipeline.execute, "__wrapped__")
        assert hasattr(AgentPipeline.handle_followup, "__wrapped__")


# ============================================================
# 5. Environment Variable Configuration
# ============================================================

class TestEnvVarConfiguration:
    """Test tracing env var handling"""

    def test_tracing_env_default_disabled(self):
        """Tracing should be disabled by default"""
        from src.core.config_manager import ConfigManager

        config = ConfigManager()
        # Default value from env should be False
        assert config.agentscope_enable_tracing is False

    def test_tracing_env_enabled(self):
        """Tracing should be enabled when env var is set"""
        import os
        old_value = os.environ.get("AGENTSCOPE_ENABLE_TRACING")
        try:
            os.environ["AGENTSCOPE_ENABLE_TRACING"] = "true"
            from src.core.config_manager import ConfigManager

            config = ConfigManager()
            assert config.agentscope_enable_tracing is True
        finally:
            if old_value is None:
                os.environ.pop("AGENTSCOPE_ENABLE_TRACING", None)
            else:
                os.environ["AGENTSCOPE_ENABLE_TRACING"] = old_value

    def test_tracing_url_default_empty(self):
        """Tracing URL should be empty by default"""
        from src.core.config_manager import ConfigManager

        config = ConfigManager()
        assert config.agentscope_tracing_url == ""


# ============================================================
# 6. Span Attribute Injector
# ============================================================

class TestSpanAttributeInjector:
    """Test the custom SpanProcessor that injects run metadata"""

    def test_span_injector_set_attributes(self):
        """SpanAttributeInjector should set expected attributes"""
        from src.core.span_injector import SpanAttributeInjector

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        injector = SpanAttributeInjector(
            run_id="test_run",
            service_name="Test Service",
        )
        injector.on_start(mock_span)

        mock_span.set_attribute.assert_any_call("gen_ai.conversation.id", "test_run")
        mock_span.set_attribute.assert_any_call("project.run_id", "test_run")
        mock_span.set_attribute.assert_any_call("service.name", "Test Service")

    def test_span_injector_handles_none_span(self):
        """SpanAttributeInjector should not crash on None span"""
        from src.core.span_injector import SpanAttributeInjector

        injector = SpanAttributeInjector(run_id="test_run")
        injector.on_start(None)  # Should not raise

    def test_span_injector_handles_non_recording_span(self):
        """SpanAttributeInjector should skip non-recording spans"""
        from src.core.span_injector import SpanAttributeInjector

        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        injector = SpanAttributeInjector(run_id="test_run")
        injector.on_start(mock_span)
        mock_span.set_attribute.assert_not_called()

    def test_span_injector_graceful_shutdown(self):
        """SpanAttributeInjector shutdown should not raise"""
        from src.core.span_injector import SpanAttributeInjector

        injector = SpanAttributeInjector(run_id="test_run")
        injector.shutdown()  # Should not raise

    def test_span_injector_on_ending(self):
        """SpanAttributeInjector _on_ending should not raise"""
        from src.core.span_injector import SpanAttributeInjector

        mock_span = MagicMock()
        injector = SpanAttributeInjector(run_id="test_run")
        injector._on_ending(mock_span)  # Should not raise

    def test_configure_span_injector(self):
        """configure_span_injector should set the module-level run_id"""
        from src.core.span_injector import (
            configure_span_injector,
            get_injected_run_id,
        )

        # Patch at the OTel SDK level to avoid needing a real TracerProvider
        with patch("opentelemetry.trace.get_tracer_provider") as mock_get:
            # Return a non-TracerProvider mock so configure_span_injector
            # skips registration (isinstance check), but still sets the
            # module-level variable
            mock_get.return_value = MagicMock()

            configure_span_injector("patched_run")
            assert get_injected_run_id() == "patched_run"

    def test_get_injected_run_id(self):
        """get_injected_run_id should return a string (the configured run_id)"""
        from src.core.span_injector import get_injected_run_id

        result = get_injected_run_id()
        # Could be None (never configured) or a string (configured by a prior test)
        assert result is None or isinstance(result, str)


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
