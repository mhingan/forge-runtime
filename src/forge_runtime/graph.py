"""Validate execution plans before any specialist task is dispatched."""
from collections import defaultdict, deque

from forge_runtime.models import ExecutionPlan


class GraphError(ValueError):
    """An execution plan violates a runtime invariant."""


def validate_plan(
    plan: ExecutionPlan,
    known_agents: set[str],
    known_skills: set[str],
) -> None:
    if not plan.goal.strip():
        raise GraphError("Plan goal cannot be empty.")
    if not plan.tasks or len(plan.tasks) > 100:
        raise GraphError("Plan must contain between 1 and 100 tasks.")

    ids = [task.id for task in plan.tasks]
    if len(ids) != len(set(ids)):
        raise GraphError("Plan contains duplicate task IDs.")
    known_ids = set(ids)

    for task in plan.tasks:
        if task.agent not in known_agents:
            raise GraphError(
                f"Task {task.id} references unknown agent: {task.agent}"
            )
        unknown_skills = set(task.skill_names) - known_skills
        if unknown_skills:
            raise GraphError(
                f"Task {task.id} references unknown skills: {sorted(unknown_skills)}"
            )
        if task.requires_approval:
            raise GraphError(
                f"Task {task.id} requires human approval, but approval gates are not "
                "enabled in this runtime version. The task was not dispatched."
            )
        if task.id in task.dependencies:
            raise GraphError(f"Task {task.id} cannot depend on itself.")
        missing = set(task.dependencies) - known_ids
        if missing:
            raise GraphError(
                f"Task {task.id} references missing dependencies: {sorted(missing)}"
            )

    indegree = {task.id: len(task.dependencies) for task in plan.tasks}
    children: dict[str, list[str]] = defaultdict(list)
    for task in plan.tasks:
        for dependency in task.dependencies:
            children[dependency].append(task.id)

    queue = deque(task_id for task_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if visited != len(plan.tasks):
        raise GraphError("Task dependencies contain a cycle.")


def blocked_tasks(
    plan: ExecutionPlan,
    failed: set[str],
    completed: set[str],
) -> set[str]:
    """Return every nonterminal task that depends on failed work, directly or indirectly."""
    blocked: set[str] = set()
    changed = True
    while changed:
        changed = False
        for task in plan.tasks:
            if task.id in completed | failed | blocked:
                continue
            if set(task.dependencies) & (failed | blocked):
                blocked.add(task.id)
                changed = True
    return blocked
