"""Forge Master: planning, dependency-aware delegation and run lifecycle."""
from __future__ import annotations
import asyncio
from typing import Any
from forge_runtime.config import Settings
from forge_runtime.evaluation import Evaluator
from forge_runtime.graph import blocked_tasks, validate_plan
from forge_runtime.models import AgentRequest, EventLevel, RunRecord, RunStatus, RuntimeEvent, TaskRecord, TaskStatus, utc_now
from forge_runtime.providers.base import AgentProvider
from forge_runtime.registry import AgentForgeRegistry
from forge_runtime.storage import SQLiteStore


class ForgeMaster:
    """Owns orchestration decisions; specialists only receive bounded task inputs."""

    def __init__(self, registry: AgentForgeRegistry, provider: AgentProvider,
                 settings: Settings | None = None, store: SQLiteStore | None = None,
                 evaluator: Evaluator | None = None) -> None:
        self.registry = registry
        self.provider = provider
        self.settings = settings or Settings()
        self.store = store or SQLiteStore(self.settings.database_url)
        self.evaluator = evaluator or Evaluator()

    def _event(self, run_id: str, kind: str, message: str, task_id: str | None = None,
               level: EventLevel = EventLevel.INFO, data: dict[str, Any] | None = None) -> None:
        self.store.add_event(RuntimeEvent(run_id=run_id, task_id=task_id, event_type=kind,
            message=message, level=level, data=data or {}))

    async def execute(self, goal: str) -> RunRecord:
        if not goal.strip():
            raise ValueError("Goal cannot be empty.")
        self.registry.load()
        run = RunRecord(goal=goal.strip(), status=RunStatus.PLANNING, started_at=utc_now())
        self.store.save_run(run)
        self._event(run.id, "run.started", "Forge Master accepted the request.")
        try:
            available = [{"name": x.name, "description": x.description}
                         for x in self.registry.agents.values()]
            if not available:
                raise RuntimeError("AgentForge registry contains no agent roles.")
            plan = await self.provider.plan(run.goal, available)
            validate_plan(plan, set(self.registry.agents), set(self.registry.skills))
            run.plan = plan
            run.status = RunStatus.RUNNING
            self.store.save_run(run)
            self._event(run.id, "plan.created", "Validated execution plan.",
                        data={"task_count": len(plan.tasks), "provider": self.provider.name})
            records = {t.id: TaskRecord(id=t.id, run_id=run.id, title=t.title, agent=t.agent)
                       for t in plan.tasks}
            for record in records.values():
                self.store.save_task(record)
            results: dict[str, str] = {}
            completed: set[str] = set()
            failed: set[str] = set()
            semaphore = asyncio.Semaphore(self.settings.max_parallel_tasks)

            async def dispatch(task):
                record = records[task.id]
                async with semaphore:
                    agent = self.registry.get_agent(task.agent)
                    requested_skills = task.skill_names or list(agent.recommended_skills)
                    skills = [self.registry.get_skill(n) for n in requested_skills
                              if n in self.registry.skills]
                    dependencies = {key: results[key] for key in task.dependencies}
                    last_error = None
                    for attempt in range(1, task.max_attempts + 1):
                        record.status = TaskStatus.RUNNING
                        record.attempt = attempt
                        record.started_at = utc_now()
                        self.store.save_task(record)
                        self._event(run.id, "task.started", task.title, task.id,
                                    data={"role": task.agent, "attempt": attempt})
                        try:
                            result = await asyncio.wait_for(
                                self.provider.execute(AgentRequest(run_id=run.id, task=task,
                                    agent=agent, skills=skills, previous_results=dependencies,
                                    attempt=attempt)),
                                timeout=min(task.timeout_seconds, self.settings.task_timeout_seconds))
                            evaluation = self.evaluator.evaluate(task, result)
                            if not evaluation.passed:
                                raise RuntimeError("; ".join(evaluation.reasons))
                            record.status = TaskStatus.SUCCEEDED
                            record.output = result.output
                            record.error = None
                            record.finished_at = utc_now()
                            self.store.save_task(record)
                            self._event(run.id, "task.succeeded", result.summary, task.id,
                                        data={"attempt": attempt, "usage": result.usage})
                            return task.id, result.output, None
                        except Exception as exc:
                            last_error = f"{type(exc).__name__}: {exc}"
                            self._event(run.id, "task.attempt_failed", last_error, task.id,
                                        EventLevel.WARNING, {"attempt": attempt})
                    record.status = TaskStatus.FAILED
                    record.error = last_error
                    record.finished_at = utc_now()
                    self.store.save_task(record)
                    self._event(run.id, "task.failed", last_error or "Task failed.", task.id,
                                EventLevel.ERROR)
                    return task.id, None, last_error

            remaining = {t.id: t for t in plan.tasks}
            while remaining:
                for task_id in blocked_tasks(plan, failed, completed):
                    if task_id in remaining:
                        record = records[task_id]
                        record.status = TaskStatus.BLOCKED
                        record.error = "A prerequisite task failed."
                        record.finished_at = utc_now()
                        self.store.save_task(record)
                        self._event(run.id, "task.blocked", record.error, task_id, EventLevel.WARNING)
                        remaining.pop(task_id)
                ready = [task for task in remaining.values()
                         if set(task.dependencies).issubset(completed)]
                if not ready:
                    if remaining:
                        raise RuntimeError("Scheduler stalled with unresolved dependencies.")
                    break
                outcomes = await asyncio.gather(*(dispatch(task) for task in ready))
                for task_id, output, error in outcomes:
                    remaining.pop(task_id, None)
                    if error is None and output is not None:
                        completed.add(task_id)
                        results[task_id] = output
                    else:
                        failed.add(task_id)
            run.status = RunStatus.FAILED if failed else RunStatus.SUCCEEDED
            run.summary = (f"{len(completed)} succeeded; {len(failed)} failed."
                           if failed else f"All {len(completed)} task(s) succeeded.")
            run.finished_at = utc_now()
            self.store.save_run(run)
            self._event(run.id, "run.finished", run.summary)
            return run
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.summary = f"Orchestration failed: {type(exc).__name__}: {exc}"
            run.finished_at = utc_now()
            self.store.save_run(run)
            self._event(run.id, "run.failed", run.summary, level=EventLevel.ERROR)
            raise
