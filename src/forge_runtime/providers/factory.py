"""Provider factory with lazy, optional SDK imports."""
from forge_runtime.config import Settings
from forge_runtime.providers.mock import MockProvider


def create_provider(name: str, settings: Settings):
    normalized = name.strip().lower()
    if normalized == "mock":
        return MockProvider()
    if normalized == "openai":
        from forge_runtime.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=settings.openai_api_key or "",
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            workspace_root=settings.workspace_root,
        )
    if normalized == "anthropic":
        from forge_runtime.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
            workspace_root=settings.workspace_root,
        )
    raise ValueError("Unsupported provider. Choose mock, openai, or anthropic.")
