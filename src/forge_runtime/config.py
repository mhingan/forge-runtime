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
    workspace_root: Path = Path(".")
    max_parallel_tasks: int = Field(default=4, ge=1, le=64)
    task_timeout_seconds: int = Field(default=900, ge=1, le=86400)
    sandbox_enabled: bool = True
    sandbox_image: str = "forge-runtime-sandbox:latest"
    sandbox_docker_binary: str = "docker"
    sandbox_cpu_limit: float = Field(default=2.0, ge=0.25, le=16)
    sandbox_memory_mb: int = Field(default=2048, ge=256, le=32768)
    sandbox_pids_limit: int = Field(default=128, ge=32, le=2048)
    sandbox_default_timeout_seconds: int = Field(default=180, ge=1, le=600)
    sandbox_max_timeout_seconds: int = Field(default=600, ge=1, le=600)
    sandbox_output_chars: int = Field(default=24000, ge=1000, le=100000)
    sandbox_max_snapshot_files: int = Field(default=5000, ge=1, le=50000)
    sandbox_max_snapshot_mb: int = Field(default=512, ge=1, le=4096)
    default_provider: str = "mock"
    agentforge_repository: str = "https://github.com/mhingan/agent-forge"
    agentforge_ref: str = "main"
    agentforge_source: Literal["auto", "installed", "local", "github"] = "auto"
    agentforge_local_path: Path | None = None
    openai_model: str = "gpt-4.1"
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8787, ge=1, le=65535)
    api_token: str | None = None
