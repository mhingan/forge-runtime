"""Provider factory with lazy, optional SDK imports."""
from forge_mcp import MCPToolBridge

from forge_runtime.config import Settings
from forge_runtime.providers.mock import MockProvider
from forge_runtime.sandbox import DockerSandboxExecutor


def create_provider(name: str, settings: Settings):
    normalized = name.strip().lower()
    if normalized == "mock":
        return MockProvider()

    sandbox = (
        DockerSandboxExecutor(
            workspace_root=settings.workspace_root,
            image=settings.sandbox_image,
            docker_binary=settings.sandbox_docker_binary,
            cpu_limit=settings.sandbox_cpu_limit,
            memory_mb=settings.sandbox_memory_mb,
            pids_limit=settings.sandbox_pids_limit,
            default_timeout_seconds=settings.sandbox_default_timeout_seconds,
            max_timeout_seconds=settings.sandbox_max_timeout_seconds,
            output_chars=settings.sandbox_output_chars,
            network=settings.sandbox_network,
            max_snapshot_files=settings.sandbox_max_snapshot_files,
            max_snapshot_bytes=settings.sandbox_max_snapshot_mb * 1024 * 1024,
        )
        if settings.sandbox_enabled
        else None
    )
    mcp_bridge = MCPToolBridge() if settings.mcp_enabled else None

    if normalized == "openai":
        from forge_runtime.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key or "",
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            workspace_root=settings.workspace_root,
            sandbox_executor=sandbox,
            mcp_bridge=mcp_bridge,
        )
    if normalized == "anthropic":
        from forge_runtime.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
            workspace_root=settings.workspace_root,
            sandbox_executor=sandbox,
            mcp_bridge=mcp_bridge,
        )
    raise ValueError("Unsupported provider. Choose mock, openai, or anthropic.")
