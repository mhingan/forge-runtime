"""Typed contracts for plans, tasks, agents, runs and events."""
from __future__ import annotations
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class EventLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AgentDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    description: str
    path: str
    content: str
    recommended_skills: tuple[str, ...] = ()
    mode: str = "subagent"


class SkillDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    description: str
    path: str
    content: str = ""


class TaskSpec(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    title: str
    description: str
    agent: str
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=2, ge=1, le=5)
    timeout_seconds: int = Field(default=900, ge=1)
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    goal: str
    summary: str
    tasks: list[TaskSpec]
    final_acceptance_criteria: list[str] = Field(default_factory=list)


class AgentRequest(BaseModel):
    run_id: str
    task: TaskSpec
    agent: AgentDefinition
    skills: list[SkillDefinition] = Field(default_factory=list)
    project_context: str = ""
    previous_results: dict[str, str] = Field(default_factory=dict)
    attempt: int = 1


class AgentResult(BaseModel):
    output: str
    summary: str
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(BaseModel):
    id: str
    run_id: str
    title: str
    agent: str
    status: TaskStatus = TaskStatus.PENDING
    attempt: int = 0
    output: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    goal: str
    status: RunStatus = RunStatus.PENDING
    plan: ExecutionPlan | None = None
    summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RuntimeEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evt"))
    run_id: str
    task_id: str | None = None
    level: EventLevel = EventLevel.INFO
    event_type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
