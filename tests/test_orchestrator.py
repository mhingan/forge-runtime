import pytest
from forge_runtime.config import Settings
from forge_runtime.models import AgentDefinition, AgentResult, ExecutionPlan, TaskSpec
from forge_runtime.orchestrator import ForgeMaster
from forge_runtime.registry import AgentForgeRegistry
from forge_runtime.storage import SQLiteStore


class Registry(AgentForgeRegistry):
    def load(self):
        self._agents = {
            "architect": AgentDefinition(name="architect", description="Design", path="a.md", content="Role"),
            "backend-engineer": AgentDefinition(name="backend-engineer", description="Build", path="b.md", content="Role"),
        }
        self._skills = {}


class Provider:
    name = "test"
    async def plan(self, goal, available_agents):
        return ExecutionPlan(goal=goal, summary="plan", tasks=[
            TaskSpec(id="a", title="A", description="A", agent="architect"),
            TaskSpec(id="b", title="B", description="B", agent="backend-engineer", dependencies=["a"]),
        ])
    async def execute(self, request):
        return AgentResult(output=f"Output {request.task.id}", summary="done")


@pytest.mark.asyncio
async def test_successful_run(tmp_path):
    url = f"sqlite:///{tmp_path / 'runtime.db'}"
    store = SQLiteStore(url)
    runtime = ForgeMaster(Registry(), Provider(), Settings(database_url=url), store=store)
    run = await runtime.execute("Build a service")
    assert run.status.value == "succeeded"
    assert len(store.get_run(run.id)["tasks"]) == 2
