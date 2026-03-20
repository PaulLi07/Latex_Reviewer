"""
LLM 模块

提供 LLM 客户端的统一接口
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
    创建 LLM 客户端

    Args:
        provider: LLM 提供商 ('deepseek', 'openai', 'anthropic', 'zhipu')
        api_key: API 密钥
        model: 模型名称
        **kwargs: 其他参数

    Returns:
        LLM 客户端实例

    Raises:
        ValueError: 不支持的提供商
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
        raise ValueError(f"不支持的 LLM 提供商: {provider}")


__all__ = [
    "BaseLLMClient",
    "ReviewItem",
    "OpenAIClient",
    "AnthropicClient",
    "DeepSeekClient",
    "ZhipuClient",
    "create_client"
]
