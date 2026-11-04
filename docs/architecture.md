# Architecture

## Project boundary

AgentForge is the knowledge plane: reusable role definitions, skills, rules, workflows and catalogs. Forge Runtime is the execution plane: planning, graph validation, task scheduling, dispatch, evaluation, persistence and reporting. The dependency is one-way: runtime consumes registry artifacts; AgentForge does not need runtime internals.

## Principal components

### Forge Master
Creates the run, loads the available roles, asks a provider for a proposed plan, validates it, supervises task state transitions and determines terminal status.

### Registry adapter
Supports local AgentForge checkouts and GitHub raw source. It reads catalog JSON and referenced Markdown. It treats these files as instructions/data for model context, never executable code.

### Planner and providers
A provider implements planning and specialist execution. Planner output is untrusted and is parsed into typed models before graph validation. Provider SDKs are imported lazily.

### DAG scheduler
A task can run only when every dependency succeeded. Independent tasks can execute concurrently up to a configured limit. Failed tasks block all descendants. Timeouts and attempt counts are bounded.

### State and event log
SQLite stores a run snapshot, task records and chronological events. It is appropriate for local development and a single process, not a distributed worker fleet.

### Evaluator
The baseline evaluator checks that output and summary exist and obey a size limit. This is not proof of factual correctness, code quality or security. Add test-backed/domain evaluators before treating outputs as production-ready.

## Lifecycle

1. Validate request and load the registry.
2. Record the run start.
3. Ask the selected planner to create a plan.
4. Validate roles, skills, dependencies and acyclicity.
5. Persist plan and task records.
6. Dispatch each ready DAG layer.
7. Enforce concurrency, timeout and retry policies.
8. Evaluate and persist outputs.
9. Block descendants when an upstream task fails.
10. Record final outcome and event.

## Future distributed architecture

Use PostgreSQL for shared state, a durable queue for dispatch, worker leases for recovery, an artifact store for large outputs, and event streaming for the operator UI. Do not simply run multiple copies against the current SQLite store.
