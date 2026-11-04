import stat
from pathlib import Path

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
    assert "agents" in result.stdout
    assert "18 skills" in result.stdout
    assert "agentforge-toolkit:" in result.stdout



def test_sandbox_cli_commands_are_registered() -> None:
    result = runner.invoke(app, ["sandbox", "--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout
    assert "check" in result.stdout
    assert "run" in result.stdout


def test_mcp_and_auth_commands_are_registered() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mcp" in result.stdout
    assert "auth" in result.stdout


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


def test_setup_copilot_merges_mcp_config_and_installs_forge_runner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import json
    from types import SimpleNamespace

    import agentforge.core
    import forge_runtime.cli as cli

    toolkit_root = tmp_path / "agentforge"
    (toolkit_root / "agents").mkdir(parents=True)
    (toolkit_root / "agents" / "forge-runner.md").write_text("profile", encoding="utf-8")
    monkeypatch.setattr(agentforge.core, "data_root", lambda: toolkit_root)
    monkeypatch.chdir(tmp_path)

    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    mcp_config = vscode_dir / "mcp.json"
    mcp_config.write_text(
        json.dumps(
            {
                "servers": {
                    "existing": {
                        "type": "stdio",
                        "command": "existing-server",
                        "args": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    commands = []
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda command, **kwargs: (
            commands.append(command)
            or SimpleNamespace(returncode=0, stdout="Forge Runner installed", stderr="")
        ),
    )

    cli._setup_copilot()

    config = json.loads(mcp_config.read_text(encoding="utf-8"))
    assert "existing" in config["servers"]
    assert config["servers"]["forge"] == {
        "type": "stdio",
        "command": "forge",
        "args": ["mcp", "serve"],
    }
    assert commands and commands[0][1:3] == ["-m", "agentforge"]
