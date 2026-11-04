from pathlib import Path
import stat

from typer.testing import CliRunner

from forge_runtime.cli import _update_dotenv, app

runner = CliRunner()


def test_cli_help_is_available() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "multi-agent orchestration" in result.stdout.lower()
    assert "setup" in result.stdout


def test_cli_registry_validation_uses_installed_agentforge() -> None:
    result = runner.invoke(app, ["registry", "validate"])
    assert result.exit_code == 0
    assert "15 agents" in result.stdout
    assert "18 skills" in result.stdout
    assert "agentforge-toolkit:" in result.stdout



def test_sandbox_cli_commands_are_registered() -> None:
    result = runner.invoke(app, ["sandbox", "--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout
    assert "check" in result.stdout
    assert "run" in result.stdout


def test_sandbox_run_help_explains_argument_array() -> None:
    result = runner.invoke(app, ["sandbox", "run", "--help"])
    assert result.exit_code == 0
    assert "Allowlisted command" in result.stdout



def test_setup_rejects_unknown_provider_without_touching_docker() -> None:
    result = runner.invoke(app, ["setup", "--provider", "unsupported"])
    assert result.exit_code == 2
    assert "openai, anthropic or mock" in result.stdout


def test_dotenv_update_preserves_existing_values_and_restricts_permissions(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# keep this comment\n"
        "FORGE_DEFAULT_PROVIDER=mock\n"
        "OPENAI_API_KEY=old-key\n"
        "CUSTOM_SETTING=keep-me\n",
        encoding="utf-8",
    )

    _update_dotenv(
        env_file,
        {
            "FORGE_DEFAULT_PROVIDER": "openai",
            "OPENAI_API_KEY": "new-key",
        },
    )

    content = env_file.read_text(encoding="utf-8")
    assert "# keep this comment" in content
    assert "FORGE_DEFAULT_PROVIDER=openai" in content
    assert "OPENAI_API_KEY=new-key" in content
    assert "CUSTOM_SETTING=keep-me" in content
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
