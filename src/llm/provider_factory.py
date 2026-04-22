# -*- coding: utf-8 -*-
"""
LLM Provider 工厂

根据配置创建相应的 Provider 实例。
"""

from typing import Dict, Optional, Type

from src.llm.providers.base import LLMProvider
from src.llm.providers.dashscope_provider import DashScopeProvider
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.providers.ollama_provider import OllamaProvider
from src.core.logger import get_logger

logger = get_logger(__name__)

# Provider 注册表
PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {
    "dashscope": DashScopeProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def get_provider(
    provider_name: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> LLMProvider:
    """
    获取 LLM Provider 实例

    Args:
        provider_name: 提供商名称 (dashscope/openai/ollama)
        api_key: API Key
        model: 模型名称
        base_url: 自定义 API 基础 URL
        **kwargs: 其他参数

    Returns:
        LLMProvider 实例

    Raises:
        ValueError: 不支持的提供商名称
    """
    provider_class = PROVIDER_REGISTRY.get(provider_name.lower())

    if provider_class is None:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unsupported provider: {provider_name}. Available: {available}"
        )

    # 构建初始化参数
    init_kwargs = {}
    if api_key:
        init_kwargs["api_key"] = api_key
    if model:
        init_kwargs["model"] = model
    if base_url:
        init_kwargs["base_url"] = base_url
    init_kwargs.update(kwargs)

    logger.info(f"Creating {provider_name} provider")
    return provider_class(**init_kwargs)


def list_available_providers() -> list:
    """获取可用的提供商列表"""
    return list(PROVIDER_REGISTRY.keys())


def register_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    """
    注册自定义 Provider

    Args:
        name: 提供商名称
        provider_class: Provider 类
    """
    PROVIDER_REGISTRY[name.lower()] = provider_class
    logger.info(f"Registered provider: {name}")
