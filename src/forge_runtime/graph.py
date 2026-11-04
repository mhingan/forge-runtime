"""Validate execution DAGs and identify descendants blocked by failures."""
from collections import defaultdict, deque
from forge_runtime.models import ExecutionPlan


class GraphError(ValueError):
    """Invalid task graph."""


def validate_plan(plan: ExecutionPlan, known_agents: set[str], known_skills: set[str]) -> None:
    if not plan.goal.strip():
        raise GraphError("Plan goal cannot be empty.")
    if not plan.tasks or len(plan.tasks) > 100:
        raise GraphError("Plan must contain between 1 and 100 tasks.")
    ids = [task.id for task in plan.tasks]
    if len(ids) != len(set(ids)):
        raise GraphError("Plan contains duplicate task IDs.")
    known = set(ids)
    for task in plan.tasks:
        if task.agent not in known_agents:
            raise GraphError(f"Task {task.id} references unknown agent: {task.agent}")
        missing_skills = set(task.skill_names) - known_skills
        if missing_skills:
            raise GraphError(f"Task {task.id} references unknown skills: {sorted(missing_skills)}")
        if task.id in task.dependencies:
            raise GraphError(f"Task {task.id} depends on itself.")
        missing = set(task.dependencies) - known
        if missing:
            raise GraphError(f"Task {task.id} has missing dependencies: {sorted(missing)}")
    degree = {task.id: len(task.dependencies) for task in plan.tasks}
    children: dict[str, list[str]] = defaultdict(list)
    for task in plan.tasks:
        for dep in task.dependencies:
            children[dep].append(task.id)
    queue = deque(node for node, count in degree.items() if count == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in children[node]:
            degree[child] -= 1
            if degree[child] == 0:
                queue.append(child)
    if visited != len(plan.tasks):
        raise GraphError("Task dependencies contain a cycle.")


def blocked_tasks(plan: ExecutionPlan, failed: set[str], completed: set[str]) -> set[str]:
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
