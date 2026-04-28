# -*- coding: utf-8 -*-
"""
LLM Provider abstract layer

Provides a unified LLM interface supporting hot-swapping across backends:
- DashScope (Alibaba Cloud Bailian)
- OpenAI
- Ollama (local deployment)

Uses the Strategy pattern + Factory pattern, conforming to the OCP principle.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMProvider(ABC):
    """
    LLM provider abstract base class

    All LLM providers must implement this interface, providing a unified chat method.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name"""
        pass

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Send messages and return the response text

        Args:
            messages: Message list, each item contains role and content
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Response text
        """
        pass

    @abstractmethod
    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Asynchronously send messages and return the response text

        Args:
            messages: Message list
            **kwargs: Additional parameters

        Returns:
            Response text
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "provider": self.provider_name,
            "models": self.get_available_models(),
        }

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return []
