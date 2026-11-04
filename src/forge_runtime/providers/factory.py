"""Provider factory with lazy, optional SDK imports."""
import os

from forge_runtime.config import Settings
from forge_runtime.providers.mock import MockProvider


def create_provider(name: str, settings: Settings):
    normalized = name.strip().lower()
    if normalized == "mock":
        return MockProvider()
    if normalized == "openai":
        from forge_runtime.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=settings.openai_model,
            base_url=settings.openai_base_url or os.getenv("OPENAI_BASE_URL"),
        )
    if normalized == "anthropic":
        from forge_runtime.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=settings.anthropic_model,
        )
    raise ValueError("Unsupported provider. Choose mock, openai, or anthropic.")
