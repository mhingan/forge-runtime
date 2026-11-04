"""Deterministic provider for development and tests."""
from forge_runtime.models import AgentRequest, AgentResult, ExecutionPlan, TaskSpec


class MockProvider:
    name = "mock"

    async def plan(self, goal: str, available_agents: list[dict[str, str]]) -> ExecutionPlan:
        names = {item["name"] for item in available_agents}
        architect = "architect" if "architect" in names else available_agents[0]["name"]
        backend = "backend-engineer" if "backend-engineer" in names else architect
        tester = "test-engineer" if "test-engineer" in names else architect
        return ExecutionPlan(goal=goal, summary="Deterministic three-stage demo plan.", tasks=[
            TaskSpec(id="design", title="Design the approach", description=f"Analyze and design a solution for: {goal}", agent=architect),
            TaskSpec(id="implementation", title="Prepare implementation guidance", description=f"Translate the design into implementation guidance: {goal}", agent=backend, dependencies=["design"]),
            TaskSpec(id="verification", title="Review the proposal", description="Identify gaps, risks and validation activities.", agent=tester, dependencies=["implementation"]),
        ], final_acceptance_criteria=["All tasks complete successfully."])

    async def execute(self, request: AgentRequest) -> AgentResult:
        prior = "\\n".join(f"- {key}: {value}" for key, value in request.previous_results.items())
        output = (f"# {request.task.title}\\n\\nRole: {request.agent.name}\\n\\n"
                  f"Task: {request.task.description}\\n\\nPrior work:\\n{prior or 'None'}\\n\\n"
                  "Mock output: this validates the orchestration path only; it is not a real implementation.")
        return AgentResult(output=output, summary=f"Mock completed: {request.task.title}", metadata={"provider": "mock", "mock": True})
