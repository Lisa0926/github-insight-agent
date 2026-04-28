# -*- coding: utf-8 -*-
"""
Ollama Provider (local deployment)

Implements the Ollama local LLM deployment provider.
"""

from typing import Any, Dict, List

from src.llm.providers.base import LLMProvider
from src.core.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider (local deployment)
    """

    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
    ):
        """
        Initialize Ollama Provider

        Args:
            model: Default model name
            base_url: Ollama server address
        """
        self.model = model
        self.base_url = base_url

    @property
    def provider_name(self) -> str:
        return "ollama"

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Synchronous chat method"""
        try:
            import requests

            # Convert message format to Ollama format
            ollama_messages = []
            for msg in messages:
                ollama_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {
                        "temperature": kwargs.get("temperature", 0.7),
                        "num_predict": kwargs.get("max_tokens", 2048),
                    },
                },
                timeout=120,
            )
            response.raise_for_status()

            # Extract response
            result = response.json()
            content = result.get("message", {}).get("content", "")
            logger.debug(f"Ollama response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            raise

    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Asynchronous chat method"""
        import aiohttp

        try:
            # Convert message format
            ollama_messages = []
            for msg in messages:
                ollama_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": kwargs.get("model", self.model),
                        "messages": ollama_messages,
                        "stream": False,
                        "options": {
                            "temperature": kwargs.get("temperature", 0.7),
                            "num_predict": kwargs.get("max_tokens", 2048),
                        },
                    },
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    result = await resp.json()
                    content = result.get("message", {}).get("content", "")
                    logger.debug(f"Ollama async response length: {len(content)}")
                    return content

        except Exception as e:
            logger.error(f"Ollama async chat failed: {e}")
            raise

    def get_available_models(self) -> List[str]:
        # Actual available models must be fetched from the Ollama server
        return ["llama2", "llama3", "mistral", "mixtral", "qwen", "qwen2"]
