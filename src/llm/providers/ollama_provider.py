# -*- coding: utf-8 -*-
"""
Ollama Provider (本地部署)

实现 Ollama 本地 LLM 部署提供商。
"""

from typing import Any, Dict, List

from src.llm.providers.base import LLMProvider
from src.core.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama LLM 提供商（本地部署）
    """

    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
    ):
        """
        初始化 Ollama Provider

        Args:
            model: 默认模型名称
            base_url: Ollama 服务器地址
        """
        self.model = model
        self.base_url = base_url

    @property
    def provider_name(self) -> str:
        return "ollama"

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """同步聊天方法"""
        try:
            import requests

            # 转换消息格式为 Ollama 格式
            ollama_messages = []
            for msg in messages:
                ollama_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

            # 调用 Ollama API
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

            # 提取响应
            result = response.json()
            content = result.get("message", {}).get("content", "")
            logger.debug(f"Ollama response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            raise

    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """异步聊天方法"""
        import aiohttp

        try:
            # 转换消息格式
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
        # 实际可用模型需要从 Ollama 服务器获取
        return ["llama2", "llama3", "mistral", "mixtral", "qwen", "qwen2"]
