"""Forge Runtime command-line interface."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from forge_runtime.config import Settings
from forge_runtime.orchestrator import ForgeMaster
from forge_runtime.providers.factory import create_provider
from forge_runtime.registry import AgentForgeRegistry, RegistryError
from forge_runtime.sandbox import DockerSandboxExecutor, SandboxError
from forge_runtime.storage import SQLiteStore

app = typer.Typer(name="forge", help="Forge Runtime — multi-agent orchestration.")
registry_cli = typer.Typer(help="Inspect the AgentForge registry.")
agent_cli = typer.Typer(help="Inspect specialist agents.")
skill_cli = typer.Typer(help="Inspect skills.")
rule_cli = typer.Typer(help="Inspect engineering rules.")
workflow_cli = typer.Typer(help="Inspect delivery workflows.")
runs_cli = typer.Typer(help="Inspect orchestration runs.")
sandbox_cli = typer.Typer(help="Build and operate the isolated Docker command sandbox.")
app.add_typer(registry_cli, name="registry")
app.add_typer(agent_cli, name="agent")
app.add_typer(skill_cli, name="skill")
app.add_typer(rule_cli, name="rule")
app.add_typer(workflow_cli, name="workflow")
app.add_typer(runs_cli, name="runs")
app.add_typer(sandbox_cli, name="sandbox")
console = Console()


def _update_dotenv(path: Path, values: dict[str, str]) -> None:
    """Atomically update selected keys without overwriting unrelated settings."""
    if path.is_symlink():
        raise ValueError(f"Refusing to write through a symlink: {path}")
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    output: list[str] = []
    for line in existing:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in pending:
                output.append(f"{key}={pending.pop(key)}")
                continue
        output.append(line)
    for key, value in pending.items():
        if "\\n" in value or "\\r" in value:
            raise ValueError(f"Environment value for {key} cannot contain a newline.")
        output.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".forge-env-",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary.write("\n".join(output) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


@app.command("setup")
def setup(
    provider: str = typer.Option(
        "openai",
        "--provider",
        help="Model provider to configure: openai, anthropic or mock.",
    ),
) -> None:
    """Configure a provider and build the Docker sandbox in one step."""
    normalized = provider.strip().lower()
    if normalized not in {"openai", "anthropic", "mock"}:
        console.print("[red]Provider must be openai, anthropic or mock.[/red]")
        raise typer.Exit(2)

    sdk_name = {"openai": "openai", "anthropic": "anthropic"}.get(normalized)
    if sdk_name and importlib.util.find_spec(sdk_name) is None:
        extra = "openai" if normalized == "openai" else "anthropic"
        console.print(
            f'[red]Provider SDK missing.[/red] Install it with: pip install -e ".[{extra}]"'
        )
        raise typer.Exit(2)

    cfg = Settings()
    updates = {"FORGE_DEFAULT_PROVIDER": normalized}
    if cfg.sandbox_image == "forge-runtime-sandbox:latest":
        updates["FORGE_SANDBOX_IMAGE"] = "forge-runtime-sandbox:internet-v1"
    if normalized == "openai" and not cfg.openai_api_key:
        key = typer.prompt("OpenAI API key", hide_input=True, confirmation_prompt=True).strip()
        if not key:
            console.print("[red]An OpenAI API key is required.[/red]")
            raise typer.Exit(2)
        updates["OPENAI_API_KEY"] = key
    elif normalized == "anthropic" and not cfg.anthropic_api_key:
        key = typer.prompt("Anthropic API key", hide_input=True, confirmation_prompt=True).strip()
        if not key:
            console.print("[red]An Anthropic API key is required.[/red]")
            raise typer.Exit(2)
        updates["ANTHROPIC_API_KEY"] = key

    try:
        _update_dotenv(Path.cwd() / ".env", updates)
        executor = get_sandbox()
        status = asyncio.run(executor.check())
        if not status["image_available"]:
            console.print(f"Building [bold]{executor.image}[/bold]...")
            output = asyncio.run(executor.build_image())
            if output.strip():
                console.print(output)
        final_status = asyncio.run(executor.check())
        if not final_status["image_available"]:
            raise SandboxError("Docker image build finished but the image is still unavailable.")
        if executor.network == "bridge":
            internet = asyncio.run(
                executor.run(
                    [
                        "curl",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "--max-time",
                        "15",
                        "-I",
                        "https://pypi.org",
                    ],
                    writable=False,
                    timeout_seconds=20,
                )
            )
            if internet.exit_code != 0:
                detail = internet.stderr.strip() or internet.stdout.strip()
                raise SandboxError(
                    "The Docker bridge is enabled but internet access could not be verified. "
                    "Check your firewall, VPN or proxy settings. "
                    f"curl output: {detail[:1000]}"
                )
    except (SandboxError, OSError, ValueError, TimeoutError) as exc:
        console.print(f"[red]Setup failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(
        f"[green]Forge Runtime is ready.[/green] Provider: [bold]{normalized}[/bold]. "
        f"Sandbox network: [bold]{executor.network}[/bold]."
    )
    console.print('Start with: [bold]forge run "Describe the project task"[/bold]')


def get_sandbox() -> DockerSandboxExecutor:
    cfg = Settings()
    return DockerSandboxExecutor(
        workspace_root=cfg.workspace_root,
        image=cfg.sandbox_image,
        docker_binary=cfg.sandbox_docker_binary,
        cpu_limit=cfg.sandbox_cpu_limit,
        memory_mb=cfg.sandbox_memory_mb,
        pids_limit=cfg.sandbox_pids_limit,
        default_timeout_seconds=cfg.sandbox_default_timeout_seconds,
        max_timeout_seconds=cfg.sandbox_max_timeout_seconds,
        output_chars=cfg.sandbox_output_chars,
        network=cfg.sandbox_network,
        max_snapshot_files=cfg.sandbox_max_snapshot_files,
        max_snapshot_bytes=cfg.sandbox_max_snapshot_mb * 1024 * 1024,
    )


@sandbox_cli.command("check")
def sandbox_check() -> None:
    executor = get_sandbox()
    try:
        status = asyncio.run(executor.check())
    except SandboxError as exc:
        console.print(f"[red]Sandbox unavailable:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(f"[green]Docker Engine:[/green] {status['docker_server_version']}")
    console.print(f"[bold]Workspace:[/bold] {status['workspace']}")
    if status["image_available"]:
        console.print(f"[green]Sandbox image ready:[/green] {status['image']}")
    else:
        console.print(f"[yellow]Image missing:[/yellow] {status['image']}")
        console.print("Run [bold]forge sandbox build[/bold] to build it.")


@sandbox_cli.command("build")
def sandbox_build() -> None:
    executor = get_sandbox()
    console.print(f"Building [bold]{executor.image}[/bold]...")
    try:
        output = asyncio.run(executor.build_image())
    except (SandboxError, TimeoutError) as exc:
        console.print(f"[red]Sandbox image build failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    if output.strip():
        console.print(output)


@sandbox_cli.command("run")
def sandbox_run(
    argv: list[str] = typer.Argument(..., help="Allowlisted command and arguments."),
    timeout_seconds: int | None = typer.Option(None, min=1, max=600),
    read_write: bool = typer.Option(
        False,
        "--read-write",
        help="Copy modified files back to the project (use only for trusted local runs).",
    ),
) -> None:
    executor = get_sandbox()
    try:
        result = asyncio.run(
            executor.run(
                argv,
                writable=read_write,
                timeout_seconds=timeout_seconds,
            )
        )
    except SandboxError as exc:
        console.print(f"[red]Sandbox execution failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print_json(json.dumps(result.as_dict(), ensure_ascii=False))
    if result.exit_code != 0:
        raise typer.Exit(result.exit_code or 1)


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
