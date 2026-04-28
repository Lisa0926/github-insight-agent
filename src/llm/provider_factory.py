# -*- coding: utf-8 -*-
"""
LLM Provider factory

Creates the corresponding Provider instance based on configuration.
"""

from typing import Dict, Optional, Type

from src.llm.providers.base import LLMProvider
from src.llm.providers.dashscope_provider import DashScopeProvider
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.providers.ollama_provider import OllamaProvider
from src.core.logger import get_logger

logger = get_logger(__name__)

# Provider registry
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
    Get an LLM Provider instance

    Args:
        provider_name: Provider name (dashscope/openai/ollama)
        api_key: API Key
        model: Model name
        base_url: Custom API base URL
        **kwargs: Additional parameters

    Returns:
        LLMProvider instance

    Raises:
        ValueError: Unsupported provider name
    """
    provider_class = PROVIDER_REGISTRY.get(provider_name.lower())

    if provider_class is None:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unsupported provider: {provider_name}. Available: {available}"
        )

    # Build initialization parameters
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
    """Get list of available providers"""
    return list(PROVIDER_REGISTRY.keys())


def register_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    """
    Register a custom Provider

    Args:
        name: Provider name
        provider_class: Provider class
    """
    PROVIDER_REGISTRY[name.lower()] = provider_class
    logger.info(f"Registered provider: {name}")
