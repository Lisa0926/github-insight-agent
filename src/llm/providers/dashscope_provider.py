# -*- coding: utf-8 -*-
"""
DashScope Provider (阿里云百炼)

实现阿里云百炼 LLM 提供商。
"""

import asyncio
from typing import Any, Dict, List, Optional

from src.llm.providers.base import LLMProvider
from src.core.logger import get_logger

logger = get_logger(__name__)


class DashScopeProvider(LLMProvider):
    """
    DashScope (阿里云百炼) LLM 提供商
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "qwen-max"):
        """
        初始化 DashScope Provider

        Args:
            api_key: API Key（不传则从环境变量读取）
            model: 默认模型名称
        """
        self.api_key = api_key
        self.model = model

    @property
    def provider_name(self) -> str:
        return "dashscope"

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """同步聊天方法"""
        try:
            import dashscope
            from dashscope import Generation

            # 设置 API Key
            if self.api_key:
                dashscope.api_key = self.api_key

            # 调用模型
            response = Generation.call(
                model=kwargs.get("model", self.model),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7),
            )

            # 提取响应
            content = self._extract_content(response)
            logger.debug(f"DashScope response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"DashScope chat failed: {e}")
            raise

    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """异步聊天方法"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.chat(messages, **kwargs),
        )

    def _extract_content(self, response) -> str:
        """提取响应内容"""
        if hasattr(response, "output") and response.output:
            output_dict = response.output if isinstance(response.output, dict) else {}
            content = output_dict.get("text", "")

            if not content and hasattr(response.output, "choices"):
                content = response.output.choices[0].message.content

            return content or ""

        return ""

    def get_available_models(self) -> List[str]:
        return ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"]
