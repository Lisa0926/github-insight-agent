# -*- coding: utf-8 -*-
"""
OpenTelemetry span attribute injector for GIA.

Registers a custom SpanProcessor that injects run_id as gen_ai.conversation.id
into every span, allowing AgentScope Studio to link spans to the correct run.
"""

from typing import Optional

# Module-level run_id, set by configure_span_injector()
_injected_run_id: Optional[str] = None
_injected_service_name: Optional[str] = None


class SpanAttributeInjector:
    """OpenTelemetry SpanProcessor that injects run metadata into every span.

    Implements the SpanProcessor interface (on_start, on_end, shutdown,
    force_flush) without inheriting from the SDK class, to avoid import-time
    coupling to the OTel SDK.
    """

    def __init__(
        self,
        run_id: str,
        service_name: str = "GitHub Insight Agent",
    ):
        self.run_id = run_id
        self.service_name = service_name

    def on_start(self, span, parent_context=None) -> None:
        """Inject attributes when a span starts."""
        try:
            if span and span.is_recording():
                span.set_attribute("gen_ai.conversation.id", self.run_id)
                span.set_attribute("service.name", self.service_name)
                span.set_attribute("project.run_id", self.run_id)
                span.set_attribute("project.service_name", self.service_name)
        except Exception:
            pass  # Graceful degradation — tracing failures must not affect main flow

    def _on_ending(self, span) -> None:
        """Called before the span ends (sync, before on_end)."""
        # No-op: on_start already injected the attributes
        pass

    def on_end(self, span, parent_context=None) -> None:
        """Called after the span ends."""
        # No-op: we only inject attributes on span start
        pass

    def shutdown(self) -> None:
        """No-op: no resources to release."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """No-op: no buffered data."""
        return True


def configure_span_injector(run_id: str, service_name: str = "GitHub Insight Agent") -> None:
    """
    Configure the span attribute injector.

    Must be called AFTER agentscope.init() (which sets up the TracerProvider).

    Registers a SpanProcessor that injects gen_ai.conversation.id and
    service.name into every span, enabling Studio to link spans to the run.

    Args:
        run_id: AgentScope run identifier (same as config.agentscope_run_name)
        service_name: Service name for span resource identification
    """
    global _injected_run_id, _injected_service_name
    _injected_run_id = run_id
    _injected_service_name = service_name

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        provider = trace.get_tracer_provider()
        # Only register if we have a TracerProvider (set up by agentscope.init())
        if isinstance(provider, TracerProvider):
            injector = SpanAttributeInjector(run_id=run_id, service_name=service_name)
            provider.add_span_processor(injector)
    except Exception:
        pass  # Graceful degradation


def get_injected_run_id() -> Optional[str]:
    """Return the currently configured run_id, or None."""
    return _injected_run_id
