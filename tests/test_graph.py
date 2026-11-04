import pytest

from forge_runtime.graph import GraphError, validate_plan
from forge_runtime.models import ExecutionPlan, TaskSpec


def plan(tasks):
    return ExecutionPlan(goal="test", summary="test", tasks=tasks)


def test_accepts_valid_dag():
    validate_plan(plan([TaskSpec(id="a", title="A", description="", agent="architect"),
        TaskSpec(id="b", title="B", description="", agent="architect", dependencies=["a"])]),
        {"architect"}, set())


def test_rejects_duplicate_ids():
    with pytest.raises(GraphError, match="Duplicate"):
        validate_plan(plan([TaskSpec(id="a", title="A", description="", agent="architect"),
            TaskSpec(id="a", title="B", description="", agent="architect")]), {"architect"}, set())


def test_rejects_cycles():
    with pytest.raises(GraphError, match="cycle"):
        validate_plan(plan([TaskSpec(id="a", title="A", description="", agent="architect", dependencies=["b"]),
            TaskSpec(id="b", title="B", description="", agent="architect", dependencies=["a"])]),
            {"architect"}, set())


def test_rejects_missing_role():
    with pytest.raises(GraphError, match="Unknown agent"):
        validate_plan(plan([TaskSpec(id="a", title="A", description="", agent="missing")]), set(), set())
