"""Baseline output checks; replace or extend for domain-specific quality gates."""
from dataclasses import dataclass
from forge_runtime.models import AgentResult, TaskSpec


@dataclass(frozen=True)
class Evaluation:
    passed: bool
    reasons: tuple[str, ...]


class Evaluator:
    def evaluate(self, task: TaskSpec, result: AgentResult) -> Evaluation:
        reasons = []
        if not result.output.strip():
            reasons.append("Output is empty.")
        if not result.summary.strip():
            reasons.append("Summary is empty.")
        if len(result.output) > 100_000:
            reasons.append("Output exceeds 100,000 characters.")
        return Evaluation(passed=not reasons, reasons=tuple(reasons))
