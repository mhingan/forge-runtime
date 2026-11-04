from typer.testing import CliRunner

from forge_runtime.cli import app


runner = CliRunner()


def test_cli_help_is_available() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "multi-agent orchestration" in result.stdout.lower()


def test_cli_registry_validation_uses_installed_agentforge() -> None:
    result = runner.invoke(app, ["registry", "validate"])
    assert result.exit_code == 0
    assert "15 agents" in result.stdout
    assert "18 skills" in result.stdout
    assert "agentforge-toolkit:" in result.stdout
