"""Environment-backed runtime configuration."""
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORGE_", env_file=".env", extra="ignore")
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./.forge/forge.db"
    max_parallel_tasks: int = Field(default=4, ge=1, le=64)
    task_timeout_seconds: int = Field(default=900, ge=1, le=86400)
    default_provider: str = "mock"
    agentforge_repository: str = "https://github.com/mhingan/agent-forge"
    agentforge_ref: str = "main"
    agentforge_source: Literal["auto", "installed", "local", "github"] = "auto"
    agentforge_local_path: Path | None = None
    openai_model: str = "gpt-4.1"
    openai_base_url: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8787, ge=1, le=65535)
    api_token: str | None = None
