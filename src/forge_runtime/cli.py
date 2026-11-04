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
registry_cli = typer.Typer(help="Inspect AgentForge source.")
agent_cli = typer.Typer(help="Inspect specialist agents.")
skill_cli = typer.Typer(help="Inspect skills.")
runs_cli = typer.Typer(help="Inspect run history.")
app.add_typer(registry_cli, name="registry")
app.add_typer(agent_cli, name="agent")
app.add_typer(skill_cli, name="skill")
app.add_typer(runs_cli, name="runs")
console = Console()


def get_registry(path: Path | None = None) -> AgentForgeRegistry:
    cfg = Settings()
    registry = AgentForgeRegistry(local_path=path or cfg.agentforge_local_path,
        repository=cfg.agentforge_repository, ref=cfg.agentforge_ref)
    registry.load()
    return registry


@registry_cli.command("validate")
def registry_validate(registry_path: Path | None = typer.Option(None, "--registry-path")) -> None:
    try:
        registry = get_registry(registry_path)
        console.print(f"[green]Valid registry:[/green] {len(registry.agents)} roles, "
                      f"{len(registry.skills)} skills.")
    except RegistryError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@agent_cli.command("list")
def agent_list(registry_path: Path | None = typer.Option(None, "--registry-path")) -> None:
    registry = get_registry(registry_path)
    table = Table("Agent", "Description")
    for agent in registry.agents.values():
        table.add_row(agent.name, agent.description)
    console.print(table)


@agent_cli.command("show")
def agent_show(name: str, registry_path: Path | None = typer.Option(None, "--registry-path")) -> None:
    agent = get_registry(registry_path).get_agent(name)
    console.print(f"[bold]{agent.name}[/bold]\n{agent.description}\n\n{agent.content}")


@skill_cli.command("list")
def skill_list(registry_path: Path | None = typer.Option(None, "--registry-path")) -> None:
    registry = get_registry(registry_path)
    table = Table("Skill", "Description")
    for skill in registry.skills.values():
        table.add_row(skill.name, skill.description)
    console.print(table)


@app.command("run")
def run(goal: str = typer.Argument(...), provider: str = typer.Option("mock", "--provider"),
        registry_path: Path | None = typer.Option(None, "--registry-path"),
        max_parallel: int = typer.Option(4, min=1, max=64)) -> None:
    cfg = Settings(max_parallel_tasks=max_parallel)
    registry = AgentForgeRegistry(local_path=registry_path or cfg.agentforge_local_path,
        repository=cfg.agentforge_repository, ref=cfg.agentforge_ref)
    runtime = ForgeMaster(registry, create_provider(provider, cfg), settings=cfg)
    result = asyncio.run(runtime.execute(goal))
    console.print(f"[bold]Run:[/bold] {result.id}")
    console.print(f"[bold]Status:[/bold] {result.status.value}")
    console.print(result.summary)


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
