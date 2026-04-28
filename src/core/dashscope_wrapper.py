# -*- coding: utf-8 -*-
"""
Synchronous DashScope model caller

Compatible with AgentScope DashScopeChatModel interface, using dashscope.Generation.call() (synchronous).
Resolves DashScopeChatModel async compatibility issues.
"""

import os
import os
from typing import Any, Dict, List

import dashscope
from dashscope import Generation

from src.core.logger import get_logger

logger = get_logger(__name__)


class DashScopeWrapper:
    """
    Synchronous DashScope model caller

    Interface compatible with AgentScope DashScopeChatModel, accepts OpenAI-format messages,
    returns ChatResponse (dict subclass).
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

    def __call__(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Call the model

        Args:
            messages: Messages in OpenAI format
            max_tokens: Maximum output token count
            temperature: Temperature parameter

        Returns:
            ChatResponse dictionary with 'content' key
        """
        from agentscope.model._model_response import ChatResponse, ChatUsage

        try:
            resp = Generation.call(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if resp.status_code != 200:
                error_text = f"DashScope API error: {resp.code} - {resp.message}"
                logger.error(error_text)
                return ChatResponse(
                    content=error_text,
                    usage=ChatUsage(input_tokens=0, output_tokens=0, time=0),
                )

            # Extract text (GenerationOutput is a dict subclass, use .get method)
            text = resp.output.get("text", "") if isinstance(resp.output, dict) else ""

            # Extract usage (same dict pattern)
            resp_usage = getattr(resp, "usage", None)
            usage = ChatUsage(
                input_tokens=resp_usage.get("input_tokens", 0) if resp_usage else 0,
                output_tokens=resp_usage.get("output_tokens", 0) if resp_usage else 0,
                time=0,
            )

            return ChatResponse(
                content=text,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"DashScope generation failed: {e}")
            return ChatResponse(
                content=f"Error: {str(e)}",
                usage=ChatUsage(input_tokens=0, output_tokens=0, time=0),
            )
