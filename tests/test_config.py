from pathlib import Path

from forge_runtime.config import Settings


def test_provider_credentials_and_base_url_load_from_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=test-openai-key\n"
        "OPENAI_MODEL=gpt-test-model\n"
        "OPENAI_BASE_URL=https://llm.example.test/v1\n"
        "ANTHROPIC_API_KEY=test-anthropic-key\n"
        "ANTHROPIC_MODEL=claude-test-model\n"
        "FORGE_DEFAULT_PROVIDER=anthropic\n"
        "FORGE_SANDBOX_ENABLED=true\n"
        "FORGE_SANDBOX_NETWORK=none\n"
        "FORGE_SANDBOX_IMAGE=forge-test-sandbox:latest\n"
        "FORGE_SANDBOX_MEMORY_MB=1024\n"
        "FORGE_MCP_ENABLED=true\n"
        "FORGE_WORKSPACE_ROOT=.\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.openai_api_key == "test-openai-key"
    assert settings.openai_model == "gpt-test-model"
    assert settings.openai_base_url == "https://llm.example.test/v1"
    assert settings.anthropic_api_key == "test-anthropic-key"
    assert settings.anthropic_model == "claude-test-model"
    assert settings.default_provider == "anthropic"
    assert settings.sandbox_enabled is True
    assert settings.sandbox_network == "none"
    assert settings.sandbox_image == "forge-test-sandbox:latest"
    assert settings.sandbox_memory_mb == 1024
    assert settings.mcp_enabled is True



def test_sandbox_network_defaults_to_internet_bridge() -> None:
    settings = Settings(_env_file=None)
    assert settings.sandbox_network == "bridge"
    assert settings.sandbox_image == "forge-runtime-sandbox:internet-v1"
