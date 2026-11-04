"""Forge Master: planning, dependency-aware delegation and run lifecycle."""
from __future__ import annotations

import asyncio
from typing import Any

from forge_runtime.config import Settings
from forge_runtime.evaluation import Evaluator
from forge_runtime.graph import blocked_tasks, validate_plan
from forge_runtime.models import (
    AgentRequest,
    EventLevel,
    RunRecord,
    RunStatus,
    RuntimeEvent,
    TaskRecord,
    TaskStatus,
    utc_now,
)
from forge_runtime.providers.base import AgentProvider
from forge_runtime.registry import AgentForgeRegistry
from forge_runtime.storage import SQLiteStore


class ForgeMaster:
    """Owns orchestration decisions; specialist agents only receive bounded task inputs."""

    def __init__(
        self,
        registry: AgentForgeRegistry,
        provider: AgentProvider,
        settings: Settings | None = None,
        store: SQLiteStore | None = None,
        evaluator: Evaluator | None = None,
    ) -> None:
        self.registry = registry
        self.provider = provider
        self.settings = settings or Settings()
        self.store = store or SQLiteStore(self.settings.database_url)
        self.evaluator = evaluator or Evaluator()

    def _event(
        self,
        run_id: str,
        kind: str,
        message: str,
        task_id: str | None = None,
        level: EventLevel = EventLevel.INFO,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.store.add_event(
            RuntimeEvent(
                run_id=run_id,
                task_id=task_id,
                event_type=kind,
                message=message,
                level=level,
                data=data or {},
            )
        )

    def _shared_project_context(self) -> str:
        """Apply the common AgentForge rules to every delegated task."""
        sections: list[str] = []
        for filename in ("universal.md", "security.md", "ai.md", "git.md"):
            content = self.registry.rules.get(filename)
            if content:
                sections.append(f"## Engineering rule: {filename}\n{content}")
        return "\n\n".join(sections)

    async def execute(self, goal: str) -> RunRecord:
        if not goal.strip():
            raise ValueError("Goal cannot be empty.")

        self.registry.load()
        run = RunRecord(goal=goal.strip(), status=RunStatus.PLANNING, started_at=utc_now())
        self.store.save_run(run)
        self._event(run.id, "run.started", "Forge Master accepted the request.")

        try:
            available_agents = [
                {
                    "name": agent.name,
                    "description": agent.description,
                    "mode": agent.mode,
                }
                for agent in self.registry.agents.values()
            ]
            if not available_agents:
                raise RuntimeError("AgentForge registry contains no agent roles.")

            plan = await self.provider.plan(run.goal, available_agents)
            validate_plan(plan, set(self.registry.agents), set(self.registry.skills))
            run.plan = plan
            run.status = RunStatus.RUNNING
            self.store.save_run(run)
            self._event(
                run.id,
                "plan.created",
                "Execution plan validated against the AgentForge registry.",
                data={
                    "task_count": len(plan.tasks),
                    "provider": self.provider.name,
                    "registry_source": self.registry.loaded_from,
                },
            )

            records = {
                task.id: TaskRecord(
                    id=task.id,
                    run_id=run.id,
                    title=task.title,
                    agent=task.agent,
                )
                for task in plan.tasks
            }
            for record in records.values():
                self.store.save_task(record)

            outputs: dict[str, str] = {}
            completed: set[str] = set()
            failed: set[str] = set()
            semaphore = asyncio.Semaphore(self.settings.max_parallel_tasks)
            common_context = self._shared_project_context()

            async def dispatch(task):
                record = records[task.id]
                async with semaphore:
                    agent = self.registry.get_agent(task.agent)
                    requested_skills = task.skill_names or list(agent.recommended_skills)
                    skills = [
                        self.registry.get_skill(name)
                        for name in requested_skills
                        if name in self.registry.skills
                    ]
                    dependency_outputs = {
                        dependency: outputs[dependency] for dependency in task.dependencies
                    }
                    task_context = common_context
                    workflow_name = task.metadata.get("workflow")
                    if workflow_name:
                        workflow = self.registry.workflows.get(str(workflow_name))
                        if workflow:
                            task_context += f"\n\n## Workflow: {workflow_name}\n{workflow}"

                    last_error: str | None = None
                    for attempt in range(1, task.max_attempts + 1):
                        record.status = TaskStatus.RUNNING
                        record.attempt = attempt
                        record.started_at = utc_now()
                        self.store.save_task(record)
                        self._event(
                            run.id,
                            "task.started",
                            f"Delegated '{task.title}' to {agent.name}.",
                            task.id,
                            data={"role": agent.name, "attempt": attempt},
                        )
                        try:
                            request = AgentRequest(
                                run_id=run.id,
                                task=task,
                                agent=agent,
                                skills=skills,
                                project_context=task_context,
                                previous_results=dependency_outputs,
                                attempt=attempt,
                            )
                            result = await asyncio.wait_for(
                                self.provider.execute(request),
                                timeout=min(
                                    task.timeout_seconds,
                                    self.settings.task_timeout_seconds,
                                ),
                            )
                            evaluation = self.evaluator.evaluate(task, result)
                            if not evaluation.passed:
                                raise RuntimeError("; ".join(evaluation.reasons))

                            record.status = TaskStatus.SUCCEEDED
                            record.output = result.output
                            record.error = None
                            record.finished_at = utc_now()
                            self.store.save_task(record)
                            self._event(
                                run.id,
                                "task.succeeded",
                                result.summary,
                                task.id,
                                data={
                                    "attempt": attempt,
                                    "provider": self.provider.name,
                                    "usage": result.usage,
                                    "artifact_count": len(result.artifacts),
                                },
                            )
                            return task.id, result.output, None
                        except asyncio.CancelledError:
                            record.status = TaskStatus.CANCELLED
                            record.error = "Execution was cancelled."
                            record.finished_at = utc_now()
                            self.store.save_task(record)
                            raise
                        except Exception as exc:
                            last_error = f"{type(exc).__name__}: {exc}"
                            self._event(
                                run.id,
                                "task.attempt_failed",
                                last_error,
                                task.id,
                                EventLevel.WARNING,
                                {"attempt": attempt},
                            )

                    record.status = TaskStatus.FAILED
                    record.error = last_error
                    record.finished_at = utc_now()
                    self.store.save_task(record)
                    self._event(
                        run.id,
                        "task.failed",
                        last_error or "Task failed.",
                        task.id,
                        EventLevel.ERROR,
                    )
                    return task.id, None, last_error

            remaining = {task.id: task for task in plan.tasks}
            while remaining:
                for task_id in blocked_tasks(plan, failed, completed):
                    if task_id in remaining:
                        record = records[task_id]
                        record.status = TaskStatus.BLOCKED
                        record.error = "A prerequisite task failed."
                        record.finished_at = utc_now()
                        self.store.save_task(record)
                        self._event(
                            run.id,
                            "task.blocked",
                            record.error,
                            task_id,
                            EventLevel.WARNING,
                        )
                        remaining.pop(task_id)

                ready = [
                    task
                    for task in remaining.values()
                    if set(task.dependencies).issubset(completed)
                ]
                if not ready:
                    if remaining:
                        raise RuntimeError("Scheduler stalled with unresolved task dependencies.")
                    break

                outcomes = await asyncio.gather(*(dispatch(task) for task in ready))
                for task_id, output, error in outcomes:
                    remaining.pop(task_id, None)
                    if error is None and output is not None:
                        completed.add(task_id)
                        outputs[task_id] = output
                    else:
                        failed.add(task_id)

            run.status = RunStatus.FAILED if failed else RunStatus.SUCCEEDED
            run.summary = (
                f"{len(completed)} task(s) succeeded; {len(failed)} failed."
                if failed
                else f"All {len(completed)} task(s) succeeded."
            )
            run.finished_at = utc_now()
            self.store.save_run(run)
            self._event(run.id, "run.finished", run.summary)
            return run

        except asyncio.CancelledError:
            run.status = RunStatus.CANCELLED
            run.summary = "Run was cancelled."
            run.finished_at = utc_now()
            self.store.save_run(run)
            self._event(run.id, "run.cancelled", run.summary, level=EventLevel.WARNING)
            raise
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.summary = f"Orchestration failed: {type(exc).__name__}: {exc}"
            run.finished_at = utc_now()
            self.store.save_run(run)
            self._event(run.id, "run.failed", run.summary, level=EventLevel.ERROR)
            raise
