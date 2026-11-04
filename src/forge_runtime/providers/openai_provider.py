"""Optional OpenAI adapter. No host tools or repository access are enabled."""
import json
from forge_runtime.models import AgentRequest, AgentResult, ExecutionPlan


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4.1") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError('Install with: pip install "forge-runtime[openai]"') from exc
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def _complete(self, system: str, user: str) -> str:
        response = await self.client.chat.completions.create(model=self.model, temperature=0.2,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Provider returned empty content.")
        return content

    async def plan(self, goal: str, available_agents: list[dict[str, str]]) -> ExecutionPlan:
        template = {"goal": goal, "summary": "summary", "tasks": [{"id": "design", "title": "Design", "description": "Task details", "agent": "architect", "dependencies": [], "acceptance_criteria": ["criterion"]}], "final_acceptance_criteria": ["criterion"]}
        raw = await self._complete("You are Forge Master, a cautious task planner. Return JSON only.",
            f"Use only these roles: {json.dumps(available_agents)}. Match this shape: {json.dumps(template)}. Goal: {goal}")
        try:
            return ExecutionPlan.model_validate(json.loads(raw))
        except Exception as exc:
            raise RuntimeError(f"Planner returned invalid JSON: {exc}") from exc

    async def execute(self, request: AgentRequest) -> AgentResult:
        skills = [{"name": s.name, "content": s.content[:6000]} for s in request.skills]
        prompt = (f"Task: {request.task.model_dump_json()}\\nSkills: {json.dumps(skills)[:16000]}\\n"
                  f"Dependency outputs: {json.dumps(request.previous_results)[:16000]}\\n"
                  "Produce a useful deliverable. Do not claim files changed or tests were run.")
        output = await self._complete(f"You are {request.agent.name}. Profile:\\n{request.agent.content[:14000]}", prompt)
        return AgentResult(output=output, summary=f"Completed: {request.task.title}")
