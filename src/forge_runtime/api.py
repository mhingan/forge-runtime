"""Optional local HTTP API for submitting and inspecting Forge runs."""
from __future__ import annotations

import secrets
from ipaddress import ip_address
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from forge_runtime import __version__
from forge_runtime.config import Settings
from forge_runtime.orchestrator import ForgeMaster
from forge_runtime.providers.factory import create_provider
from forge_runtime.registry import AgentForgeRegistry, RegistryError
from forge_runtime.storage import SQLiteStore

settings = Settings()
app = FastAPI(
    title="Forge Runtime API",
    version=__version__,
    description="Local API for AgentForge-backed multi-agent orchestration.",
)


class CreateRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=20_000)
    provider: str | None = None


def authorize(
    request: Request,
    x_forge_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Require a token for non-loopback clients, regardless of the server bind address."""
    if settings.api_token:
        if not x_forge_api_key or not secrets.compare_digest(
            x_forge_api_key, settings.api_token
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing Forge API key.")
        return

    client_host = request.client.host if request.client is not None else ""
    try:
        is_loopback = ip_address(client_host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise HTTPException(
            status_code=401,
            detail="Set FORGE_API_TOKEN and send X-Forge-API-Key for non-local access.",
        )


def get_store() -> SQLiteStore:
    return SQLiteStore(settings.database_url)


def get_registry() -> AgentForgeRegistry:
    return AgentForgeRegistry(
        local_path=settings.agentforge_local_path,
        repository=settings.agentforge_repository,
        ref=settings.agentforge_ref,
        source=settings.agentforge_source,
    )


def get_runtime(provider_name: str | None = None) -> ForgeMaster:
    registry = get_registry()
    provider = create_provider(provider_name or settings.default_provider, settings)
    return ForgeMaster(registry=registry, provider=provider, settings=settings)


@app.get("/health", dependencies=[Depends(authorize)])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "forge-runtime", "version": __version__}


@app.get("/v1/agents", dependencies=[Depends(authorize)])
def list_agents() -> list[dict[str, Any]]:
    try:
        registry = get_registry()
        registry.load()
    except RegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        {
            "name": agent.name,
            "description": agent.description,
            "mode": agent.mode,
            "recommended_skills": list(agent.recommended_skills),
        }
        for agent in registry.agents.values()
    ]


@app.get("/v1/skills", dependencies=[Depends(authorize)])
def list_skills() -> list[dict[str, str]]:
    try:
        registry = get_registry()
        registry.load()
    except RegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [
        {"name": skill.name, "description": skill.description, "path": skill.path}
        for skill in registry.skills.values()
    ]


@app.post("/v1/runs", status_code=201, dependencies=[Depends(authorize)])
async def create_run(payload: CreateRunRequest) -> dict[str, Any]:
    try:
        runtime = get_runtime(payload.provider)
        run = await runtime.execute(payload.goal)
        return run.model_dump(mode="json")
    except RegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Orchestration failed: {type(exc).__name__}: {exc}",
        ) from exc


@app.get("/v1/runs", dependencies=[Depends(authorize)])
def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100.")
    return get_store().list_runs(limit)


@app.get("/v1/runs/{run_id}", dependencies=[Depends(authorize)])
def get_run(run_id: str) -> dict[str, Any]:
    run = get_store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
