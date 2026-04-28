# -*- coding: utf-8 -*-
"""
DashScope Provider (Alibaba Cloud Bailian)

Implements the Alibaba Cloud Bailian LLM provider.
"""

import asyncio
from typing import Any, Dict, List, Optional

from src.llm.providers.base import LLMProvider
from src.core.logger import get_logger

logger = get_logger(__name__)


class DashScopeProvider(LLMProvider):
    """
    DashScope (Alibaba Cloud Bailian) LLM provider
    """

    def __init__(self, api_key: Optional[str] = None, model: str = ""):
        """
        Initialize DashScope Provider

        Args:
            api_key: API Key (read from environment variable if not provided)
            model: Default model name (default: from DASHSCOPE_MODEL env var)
        """
        import os
        self.model = model or os.getenv("DASHSCOPE_MODEL", "")
        self.api_key = api_key
        self.model = model

    @property
    def provider_name(self) -> str:
        return "dashscope"

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Synchronous chat method"""
        try:
            import dashscope
            from dashscope import Generation

            # Set API Key
            if self.api_key:
                dashscope.api_key = self.api_key

            # Call the model
            response = Generation.call(
                model=kwargs.get("model", self.model),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7),
            )

            # Extract response
            content = self._extract_content(response)
            logger.debug(f"DashScope response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"DashScope chat failed: {e}")
            raise

    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Asynchronous chat method"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.chat(messages, **kwargs),
        )

    def _extract_content(self, response) -> str:
        """Extract response content"""
        if hasattr(response, "output") and response.output:
            output_dict = response.output if isinstance(response.output, dict) else {}
            content = output_dict.get("text", "")

            if not content and hasattr(response.output, "choices"):
                content = response.output.choices[0].message.content

            return content or ""

        return ""

    def get_available_models(self) -> List[str]:
        return ["YOUR_MODEL_A", "YOUR_MODEL_B", "YOUR_MODEL_C", "YOUR_MODEL_D"]
