"""
LLM Module

Provides unified interface for LLM clients
"""
from .base_client import BaseLLMClient, ReviewItem
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .deepseek_client import DeepSeekClient
from .zhipu_client import ZhipuClient


def create_client(
    provider: str,
    api_key: str,
    model: str,
    **kwargs
) -> BaseLLMClient:
    """
    Create LLM client

    Args:
        provider: LLM provider ('deepseek', 'openai', 'anthropic', 'zhipu')
        api_key: API key
        model: Model name
        **kwargs: Other parameters

    Returns:
        LLM client instance

    Raises:
        ValueError: Unsupported provider
    """
    if provider.lower() == "deepseek":
        return DeepSeekClient(
            api_key=api_key,
            model=model,
            **kwargs
        )
    elif provider.lower() == "openai":
        return OpenAIClient(
            api_key=api_key,
            model=model,
            **kwargs
        )
    elif provider.lower() == "anthropic":
        return AnthropicClient(
            api_key=api_key,
            model=model,
            **kwargs
        )
    elif provider.lower() == "zhipu":
        return ZhipuClient(
            api_key=api_key,
            model=model,
            **kwargs
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


__all__ = [
    "BaseLLMClient",
    "ReviewItem",
    "OpenAIClient",
    "AnthropicClient",
    "DeepSeekClient",
    "ZhipuClient",
    "create_client"
]
