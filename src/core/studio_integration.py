# -*- coding: utf-8 -*-
"""
AgentScope Studio integration for GIA

Provides a unified interface for pushing messages to AgentScope Studio.
Uses HTTP-based forwarding (StudioHelper) for reliability — avoids asyncio.run()
pitfalls with AgentScope's async AgentBase.print() method.

The HTTP approach is simpler and more reliable:
- No event loop issues
- Works regardless of async context
- Directly calls Studio tRPC endpoints (same as StudioHelper)
"""

from src.core.studio_helper import get_studio_helper


def push_to_studio(sender: str, content: str, role: str = "assistant") -> None:
    """
    Push a message to AgentScope Studio via HTTP forwarding.

    Uses StudioHelper's HTTP-based forward_message() for reliability.
    This avoids asyncio.run() issues with AgentScope's async print().

    Args:
        sender: Sender name (e.g., 'Researcher', 'Analyst', 'user')
        content: Message content
        role: Message role ('user' or 'assistant')
    """
    helper = get_studio_helper()
    if helper is None:
        return  # Studio not configured — silent graceful degradation

    try:
        helper.forward_message(name=sender, content=content, role=role)
    except Exception:
        pass  # Graceful degradation — does not affect main flow


def flush_traces() -> None:
    """Flush OpenTelemetry traces to ensure they reach Studio."""
    try:
        from opentelemetry import trace as otel_trace
        provider = otel_trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception:
        pass
