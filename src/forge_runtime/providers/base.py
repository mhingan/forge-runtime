"""Provider protocol for plan generation and specialist task execution."""
from typing import Protocol

from forge_runtime.models import AgentRequest, AgentResult, ExecutionPlan


class AgentProvider(Protocol):
    name: str
    async def plan(self, goal: str, available_agents: list[dict[str, str]]) -> ExecutionPlan: ...
    async def execute(self, request: AgentRequest) -> AgentResult: ...
