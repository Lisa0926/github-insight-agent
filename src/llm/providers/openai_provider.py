# -*- coding: utf-8 -*-
"""
OpenAI Provider

Implements the OpenAI LLM provider.
"""

from typing import Any, Dict, List, Optional

from src.llm.providers.base import LLMProvider
from src.core.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        base_url: Optional[str] = None,
    ):
        """
        Initialize OpenAI Provider

        Args:
            api_key: API Key (read from environment variable if not provided)
            model: Default model name
            base_url: Custom API base URL (for compatibility with other OpenAI-format APIs)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @property
    def provider_name(self) -> str:
        return "openai"

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Synchronous chat method"""
        try:
            from openai import OpenAI

            # Create client
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

            # Call the model
            response = client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7),
            )

            # Extract response
            content = response.choices[0].message.content or ""
            logger.debug(f"OpenAI response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"OpenAI chat failed: {e}")
            raise

    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Asynchronous chat method"""
        try:
            from openai import AsyncOpenAI

            # Create async client
            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

            # Call the model
            response = await client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7),
            )

            # Extract response
            content = response.choices[0].message.content or ""
            logger.debug(f"OpenAI async response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"OpenAI async chat failed: {e}")
            raise

    def get_available_models(self) -> List[str]:
        return ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-3.5-turbo"]
