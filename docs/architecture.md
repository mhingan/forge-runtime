# Architecture

## System boundary

AgentForge is the knowledge plane. The published agentforge-toolkit package embeds the canonical agent profiles, skills, rules, workflows and catalogs. Forge Runtime is the execution plane. It consumes this data through agentforge.core.data_root() and owns planning, scheduling, delegation, model calls, evaluation and persisted run state.

The dependency is intentionally one-way. AgentForge does not import Forge Runtime, and Forge Runtime does not install or invoke the provider-specific coding-agent CLIs that AgentForge targets.

## Registry loading

Source selection order is configured by FORGE_AGENTFORGE_SOURCE:

- auto: use installed agentforge-toolkit data, with a GitHub fallback if the package is unavailable.
- installed: require the toolkit and use its data_root() directory.
- local: load an explicit source checkout from FORGE_AGENTFORGE_LOCAL_PATH.
- github: load catalog JSON and referenced Markdown from the selected repository ref.

The adapter maps catalog default_mode to the runtime's agent mode field. It reads agent and skill definitions as text. It also loads rules and workflow Markdown from local/package data directories. Registry paths are validated as relative paths and may not traverse outside the data root.

## Forge Master

Forge Master owns a single run lifecycle. It loads the registry, calls the selected provider planner, validates the returned plan, records tasks, schedules ready work, evaluates results, handles bounded retries and persists the terminal run status.

Specialist agents are prompt configurations, not isolated processes. In this version, each specialist invocation is a provider request with that agent's role profile, relevant skills, shared engineering rules and successful dependency outputs.

## Planning and provider boundary

The provider protocol contains two operations:

- plan(goal, available_agents) returns an ExecutionPlan.
- execute(AgentRequest) returns an AgentResult.

The mock provider produces deterministic demo outputs. OpenAI and Anthropic adapters produce LLM-backed plans and task outputs. SDK imports are lazy, so users can run mock mode without provider SDKs or keys.

## Task graph and scheduler

A plan is a directed acyclic graph. Validation rejects duplicate IDs, unknown agent roles, unknown skills, missing dependencies, self-dependencies, cycles and plans larger than the configured task cap. Tasks requiring human approval are rejected until an approval workflow exists.

At each scheduler iteration, all tasks whose dependencies have succeeded are eligible. A semaphore caps concurrency. Successful outputs are made available to direct downstream dependencies. Failed tasks are retried up to their task attempt limit. Downstream tasks are marked blocked when a prerequisite fails.

## Context assembly

Each agent receives:
- Its AgentForge specialist profile.
- Explicit task instructions and acceptance criteria.
- Skills explicitly named by the plan, or recommended skills from the agent catalog.
- Common AgentForge rules for universal engineering, security, AI and Git.
- Successful dependency results.
- Optional project context supplied through the AgentRequest contract.

An optional workflow can be selected through task metadata using a workflow filename from the loaded AgentForge directory. The selected workflow is appended to the task context.

## Persistence and events

SQLite stores run snapshots, task records, outputs, errors and event rows. This is designed for a local process and simple development deployment. It is not a durable queue, horizontally scalable database or multi-tenant storage layer.

## HTTP API

The optional FastAPI service exposes health, registry inspection, synchronous run submission, run listing and run detail endpoints. It binds to localhost by default. Network binds require FORGE_API_TOKEN and use the X-Forge-API-Key header. The run endpoint waits for orchestration to finish and returns the resulting record.

## Future production architecture

A production deployment should introduce a PostgreSQL repository, durable queue, worker leases, cancellation and idempotency, artifact storage, capability-scoped sandboxed executors, approval service, tenant-level authorization, cost budgets and streamed execution events.
