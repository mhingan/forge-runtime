"""Forge Runtime command-line interface."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from forge_runtime.config import Settings
from forge_runtime.orchestrator import ForgeMaster
from forge_runtime.providers.factory import create_provider
from forge_runtime.registry import AgentForgeRegistry, RegistryError
from forge_runtime.storage import SQLiteStore

app = typer.Typer(name="forge", help="Forge Runtime — multi-agent orchestration.")
registry_cli = typer.Typer(help="Inspect the AgentForge registry.")
agent_cli = typer.Typer(help="Inspect specialist agents.")
skill_cli = typer.Typer(help="Inspect skills.")
rule_cli = typer.Typer(help="Inspect engineering rules.")
workflow_cli = typer.Typer(help="Inspect delivery workflows.")
runs_cli = typer.Typer(help="Inspect orchestration runs.")
app.add_typer(registry_cli, name="registry")
app.add_typer(agent_cli, name="agent")
app.add_typer(skill_cli, name="skill")
app.add_typer(rule_cli, name="rule")
app.add_typer(workflow_cli, name="workflow")
app.add_typer(runs_cli, name="runs")
console = Console()


def get_registry(path: Path | None = None) -> AgentForgeRegistry:
    cfg = Settings()
    registry = AgentForgeRegistry(
        local_path=path or cfg.agentforge_local_path,
        repository=cfg.agentforge_repository,
        ref=cfg.agentforge_ref,
        source=cfg.agentforge_source,
    )
    registry.load()
    return registry


@registry_cli.command("validate")
def registry_validate(
    registry_path: Path | None = typer.Option(None, "--registry-path"),
) -> None:
    try:
        registry = get_registry(registry_path)
        console.print(
            f"[green]AgentForge registry ready:[/green] "
            f"{len(registry.agents)} agents, {len(registry.skills)} skills, "
            f"{len(registry.rules)} rules, {len(registry.workflows)} workflows."
        )
        console.print(f"[dim]Source: {registry.loaded_from}[/dim]")
    except RegistryError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@agent_cli.command("list")
def agent_list(
    registry_path: Path | None = typer.Option(None, "--registry-path"),
) -> None:
    registry = get_registry(registry_path)
    table = Table("Agent", "Mode", "Recommended skills", "Description")
    for agent in registry.agents.values():
        table.add_row(
            agent.name,
            agent.mode,
            ", ".join(agent.recommended_skills),
            agent.description,
        )
    console.print(table)


@agent_cli.command("show")
def agent_show(
    name: str,
    registry_path: Path | None = typer.Option(None, "--registry-path"),
) -> None:
    agent = get_registry(registry_path).get_agent(name)
    console.print(f"[bold]{agent.name}[/bold] ({agent.mode})")
    console.print(agent.description)
    console.print(agent.content)


@skill_cli.command("list")
def skill_list(
    registry_path: Path | None = typer.Option(None, "--registry-path"),
) -> None:
    registry = get_registry(registry_path)
    table = Table("Skill", "Description")
    for skill in registry.skills.values():
        table.add_row(skill.name, skill.description)
    console.print(table)


@rule_cli.command("list")
def rule_list(
    registry_path: Path | None = typer.Option(None, "--registry-path"),
) -> None:
    registry = get_registry(registry_path)
    for name in registry.rules:
        console.print(f"- {name}")


@workflow_cli.command("list")
def workflow_list(
    registry_path: Path | None = typer.Option(None, "--registry-path"),
) -> None:
    registry = get_registry(registry_path)
    for name in registry.workflows:
        console.print(f"- {name}")


@app.command("run")
def run(
    goal: str = typer.Argument(..., help="Outcome to plan and delegate."),
    provider: str | None = typer.Option(
        None, "--provider", help="Provider override: mock, openai or anthropic."
    ),
    registry_path: Path | None = typer.Option(None, "--registry-path"),
    max_parallel: int | None = typer.Option(None, min=1, max=64),
) -> None:
    cfg = Settings(
        max_parallel_tasks=max_parallel or Settings().max_parallel_tasks,
    )
    registry = AgentForgeRegistry(
        local_path=registry_path or cfg.agentforge_local_path,
        repository=cfg.agentforge_repository,
        ref=cfg.agentforge_ref,
        source=cfg.agentforge_source,
    )
    runtime = ForgeMaster(
        registry=registry,
        provider=create_provider(provider or cfg.default_provider, cfg),
        settings=cfg,
    )
    result = asyncio.run(runtime.execute(goal))
    console.print(f"[bold]Run:[/bold] {result.id}")
    console.print(f"[bold]Status:[/bold] {result.status.value}")
    console.print(result.summary)


@app.command("serve")
def serve(
    host: str | None = typer.Option(None, help="Bind address. Defaults to 127.0.0.1."),
    port: int | None = typer.Option(None, min=1, max=65535),
) -> None:
    cfg = Settings()
    bind_host = host or cfg.api_host
    bind_port = port or cfg.api_port
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if bind_host not in local_hosts and not cfg.api_token:
        console.print(
            "[red]Refusing a network bind without FORGE_API_TOKEN.[/red] "
            "Set a strong token in the environment or bind to 127.0.0.1."
        )
        raise typer.Exit(2)
    try:
        import uvicorn
    except ImportError as exc:
        console.print('[red]Install the API extra: pip install "forge-runtime[api]"[/red]')
        raise typer.Exit(2) from exc
    console.print(f"Forge Runtime API listening on http://{bind_host}:{bind_port}")
    uvicorn.run("forge_runtime.api:app", host=bind_host, port=bind_port)


@runs_cli.command("list")
def runs_list(limit: int = typer.Option(20, min=1, max=100)) -> None:
    table = Table("Run ID", "Status", "Goal", "Created")
    for row in SQLiteStore(Settings().database_url).list_runs(limit):
        table.add_row(row["id"], row["status"], row["goal"], row["created_at"])
    console.print(table)


@runs_cli.command("show")
def runs_show(run_id: str) -> None:
    data = SQLiteStore(Settings().database_url).get_run(run_id)
    if data is None:
        console.print("[red]Run not found.[/red]")
        raise typer.Exit(1)
    console.print_json(json.dumps(data, ensure_ascii=False, default=str))


if __name__ == "__main__":
    app()
