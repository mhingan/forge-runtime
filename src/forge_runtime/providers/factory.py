"""Provider construction from explicit runtime selection."""
import os
from forge_runtime.config import Settings
from forge_runtime.providers.mock import MockProvider


def create_provider(name: str, settings: Settings):
    if name == "mock":
        return MockProvider()
    if name == "openai":
        from forge_runtime.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(os.getenv("OPENAI_API_KEY", ""), settings.openai_model)
    if name == "anthropic":
        from forge_runtime.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(os.getenv("ANTHROPIC_API_KEY", ""), settings.anthropic_model)
    raise ValueError(f"Unsupported provider {name!r}; use mock, openai or anthropic.")
