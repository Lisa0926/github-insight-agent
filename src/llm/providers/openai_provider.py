# -*- coding: utf-8 -*-
"""
OpenAI Provider

实现 OpenAI LLM 提供商。
"""

from typing import Any, Dict, List, Optional

from src.llm.providers.base import LLMProvider
from src.core.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM 提供商
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        base_url: Optional[str] = None,
    ):
        """
        初始化 OpenAI Provider

        Args:
            api_key: API Key（不传则从环境变量读取）
            model: 默认模型名称
            base_url: 自定义 API 基础 URL（用于兼容其他 OpenAI 格式 API）
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @property
    def provider_name(self) -> str:
        return "openai"

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """同步聊天方法"""
        try:
            from openai import OpenAI

            # 创建客户端
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

            # 调用模型
            response = client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7),
            )

            # 提取响应
            content = response.choices[0].message.content or ""
            logger.debug(f"OpenAI response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"OpenAI chat failed: {e}")
            raise

    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """异步聊天方法"""
        try:
            from openai import AsyncOpenAI

            # 创建异步客户端
            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

            # 调用模型
            response = await client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7),
            )

            # 提取响应
            content = response.choices[0].message.content or ""
            logger.debug(f"OpenAI async response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"OpenAI async chat failed: {e}")
            raise

    def get_available_models(self) -> List[str]:
        return ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-3.5-turbo"]
