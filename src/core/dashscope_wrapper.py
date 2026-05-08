# -*- coding: utf-8 -*-
"""
Synchronous DashScope model caller

Compatible with AgentScope DashScopeChatModel interface, using dashscope.Generation.call() (synchronous).
Resolves DashScopeChatModel async compatibility issues.
Supports native function calling via `tools` parameter.
"""

import os
from typing import Any, Dict, List, Optional

import dashscope
from dashscope import Generation

from agentscope.message._message_block import ToolUseBlock

from src.core.logger import get_logger

# Import AgentScope tracing (graceful fallback if disabled)
try:
    from agentscope.tracing import trace
except ImportError:
    def trace(name=None):
        def decorator(func):
            return func
        return decorator

logger = get_logger(__name__)


class DashScopeWrapper:
    """
    Synchronous DashScope model caller

    Interface compatible with AgentScope DashScopeChatModel, accepts OpenAI-format messages,
    returns ChatResponse (dict subclass). Supports native function calling.
    """

    def __init__(
        self,
        model_name: str = "",
        api_key: str = "",
        base_url: str = "",
    ):
        self.model_name = model_name or os.getenv("DASHSCOPE_MODEL", "")
        self.api_key = api_key
        self.base_url = base_url

        dashscope.api_key = api_key
        if base_url:
            dashscope.base_url = base_url

    @trace(name="dashscope.call")
    def __call__(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Call the model

        Args:
            messages: Messages in OpenAI format
            max_tokens: Maximum output token count
            temperature: Temperature parameter
            tools: Optional list of OpenAI-format function tool schemas
            **kwargs: Additional arguments passed to dashscope.Generation.call

        Returns:
            ChatResponse with content as TextBlock list or ToolUseBlock list
        """
        from agentscope.model._model_response import ChatResponse, ChatUsage

        call_kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        call_kwargs.update(kwargs)

        if tools:
            call_kwargs["tools"] = tools

        try:
            resp = Generation.call(**call_kwargs)

            if resp.status_code != 200:
                error_text = f"DashScope API error: {resp.code} - {resp.message}"
                logger.error(error_text)
                return ChatResponse(
                    content=error_text,
                    usage=ChatUsage(input_tokens=0, output_tokens=0, time=0),
                    metadata={"error": error_text},
                )

            # Extract message from response
            message = resp.output.choices[0].message if resp.output.choices else {}
            text_content = message.get("text", "") if isinstance(message, dict) else ""
            tool_calls = message.get("tool_calls", []) if isinstance(message, dict) else []

            # Extract usage
            resp_usage = getattr(resp, "usage", None)
            usage = ChatUsage(
                input_tokens=resp_usage.get("input_tokens", 0) if resp_usage else 0,
                output_tokens=resp_usage.get("output_tokens", 0) if resp_usage else 0,
                time=0,
            )

            # If model returned tool calls, build ToolUseBlock content
            if tool_calls:
                content_blocks: List[Any] = []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    try:
                        import json
                        args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    content_blocks.append(
                        ToolUseBlock(
                            type="tool_use",
                            id=tc.get("id", f"call_{len(content_blocks)}"),
                            name=fn.get("name", "unknown"),
                            input=args,
                            raw_input=fn.get("arguments", "{}"),
                        )
                    )
                return ChatResponse(
                    content=content_blocks,
                    usage=usage,
                )

            # Text-only response
            return ChatResponse(
                content=text_content,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"DashScope generation failed: {e}")
            error_text = f"Error: {str(e)}"
            return ChatResponse(
                content=error_text,
                usage=ChatUsage(input_tokens=0, output_tokens=0, time=0),
                metadata={"error": error_text},
            )

    def extract_tool_calls(self, response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from a model response.

        Args:
            response: ChatResponse or dict

        Returns:
            List of tool call dicts with 'id', 'name', 'input' keys.
            Empty list if no tool calls.
        """
        if not isinstance(response, dict):
            return []

        content = response.get("content", [])
        if not isinstance(content, list):
            return []

        tool_calls = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": block.get("input", {}),
                })
            elif isinstance(block, ToolUseBlock):
                tool_calls.append({
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": getattr(block, "input", {}),
                })
        return tool_calls

    def has_tool_calls(self, response) -> bool:
        """Check if response contains tool calls."""
        return len(self.extract_tool_calls(response)) > 0
