# -*- coding: utf-8 -*-
"""
LLM Provider 抽象层

提供统一的 LLM 接口，支持多后端热切换:
- DashScope (阿里云百炼)
- OpenAI
- Ollama (本地部署)

使用策略模式 + 工厂模式，符合 OCP 原则。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMProvider(ABC):
    """
    LLM 提供商抽象基类

    所有 LLM 提供商必须实现此接口，提供统一的 chat 方法。
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """返回提供商名称"""
        pass

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        发送消息并返回响应文本

        Args:
            messages: 消息列表，每项包含 role 和 content
            **kwargs: 额外参数 (temperature, max_tokens 等)

        Returns:
            响应文本
        """
        pass

    @abstractmethod
    async def chat_async(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        异步发送消息并返回响应文本

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            响应文本
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.provider_name,
            "models": self.get_available_models(),
        }

    def get_available_models(self) -> List[str]:
        """获取可用模型列表"""
        return []
