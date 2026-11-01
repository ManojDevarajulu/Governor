"""Model provider abstractions for Governor.

Supports both local open-weight models (Ollama, vLLM) and hosted
frontier APIs (OpenAI, Anthropic, OpenRouter) via standard HTTP.
"""

from .provider import (
    BaseModelProvider,
    ModelResponse,
    MockModelProvider,
    OpenAICompatibleProvider,
    AnthropicProvider,
    get_provider,
)

__all__ = [
    "BaseModelProvider",
    "ModelResponse",
    "MockModelProvider",
    "OpenAICompatibleProvider",
    "AnthropicProvider",
    "get_provider",
]
