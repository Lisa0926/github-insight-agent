# -*- coding: utf-8 -*-
"""
AgentScope Studio integration for GIA

Provides a silent agent that pushes messages to Studio via AgentScope's
official hook mechanism (pre_print hook -> as_studio_forward_message).

This ensures Studio displays the exact same content as CLI output,
with proper message format and token usage information.
"""

import asyncio
from typing import Optional

from agentscope.agent import AgentBase
from agentscope.message import Msg


class _StudioPushAgent(AgentBase):
    """Silent agent that only pushes messages to Studio (no terminal output)."""

    def __init__(self, name: str = "GIA"):
        super().__init__()
        self.name = name
        self.set_console_output_enabled(False)

    def reply(self, msg: Msg) -> Msg:
        return msg


# Global singleton
_studio_agent: Optional[_StudioPushAgent] = None


def push_to_studio(sender: str, content: str, role: str = "assistant") -> None:
    """
    Push a message to AgentScope Studio using the official hook mechanism.

    This is the recommended way to send messages to Studio, as it ensures:
    - Content matches CLI output exactly
    - Proper AgentScope message format (content blocks, metadata, etc.)
    - Token usage info can be included in metadata

    Args:
        sender: Sender name (e.g., 'Researcher', 'Analyst', 'user')
        content: Message content
        role: Message role ('user' or 'assistant')
    """
    global _studio_agent
    if _studio_agent is None:
        _studio_agent = _StudioPushAgent()

    msg = Msg(name=sender, content=content, role=role)
    try:
        asyncio.run(_studio_agent.print(msg))
    except Exception:
        pass  # Graceful degradation - does not affect main flow


def flush_traces() -> None:
    """Flush OpenTelemetry traces to ensure they reach Studio."""
    try:
        from opentelemetry import trace as otel_trace
        provider = otel_trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception:
        pass
