"""Optional Anthropic adapter. No host tools or repository access are enabled."""
import json
from forge_runtime.models import AgentRequest, AgentResult, ExecutionPlan


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5") -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required.")
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError('Install with: pip install "forge-runtime[anthropic]"') from exc
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def _complete(self, system: str, prompt: str) -> str:
        response = await self.client.messages.create(model=self.model, max_tokens=4096, system=system, messages=[{"role": "user", "content": prompt}])
        blocks = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        if not blocks:
            raise RuntimeError("Provider returned no text.")
        return "\\n".join(blocks)

    async def plan(self, goal: str, available_agents: list[dict[str, str]]) -> ExecutionPlan:
        shape = {"goal": goal, "summary": "summary", "tasks": [{"id": "task-1", "title": "Title", "description": "Description", "agent": "architect", "dependencies": [], "acceptance_criteria": ["criterion"]}], "final_acceptance_criteria": ["criterion"]}
        raw = await self._complete("You are Forge Master. Return valid JSON only.", f"Use only these roles: {json.dumps(available_agents)}. Match {json.dumps(shape)}. Goal: {goal}")
        try:
            return ExecutionPlan.model_validate(json.loads(raw))
        except Exception as exc:
            raise RuntimeError(f"Invalid planner JSON: {exc}") from exc

    async def execute(self, request: AgentRequest) -> AgentResult:
        prompt = (f"Task: {request.task.model_dump_json()}\\nPrior work: {json.dumps(request.previous_results)[:16000]}\\n"
                  f"Skills: {json.dumps([s.content[:6000] for s in request.skills])[:16000]}\\n"
                  "Produce the deliverable without claiming unperformed tool actions.")
        output = await self._complete(f"Act as {request.agent.name}. Profile:\\n{request.agent.content[:14000]}", prompt)
        return AgentResult(output=output, summary=f"Completed: {request.task.title}")
