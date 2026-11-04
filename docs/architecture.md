# Architecture

## System boundary

AgentForge is the knowledge plane. The published agentforge-toolkit package embeds canonical specialist profiles, skills, rules, workflow playbooks and catalogs. Forge Runtime is the execution plane: planning, scheduling, delegation, model calls, workspace operations, evaluation and persisted run state.

The dependency is intentionally one-way. AgentForge does not import Forge Runtime, and Forge Runtime does not install or invoke provider-specific coding-agent CLIs that AgentForge targets.

## Registry loading

Source selection is configured by FORGE_AGENTFORGE_SOURCE:

- auto: use installed agentforge-toolkit data, with GitHub fallback if the package is unavailable.
- installed: require the toolkit and use its agentforge.core.data_root() directory.
- local: load an explicit source checkout from FORGE_AGENTFORGE_LOCAL_PATH.
- github: load catalog JSON and referenced Markdown from the selected repository ref.

The adapter maps catalog default_mode to the runtime agent mode. It loads catalogs, role Markdown, skill Markdown, linked progressive-disclosure references, rules and workflows. Registry paths must remain relative to the data root.

## Forge Master

Forge Master owns a single run lifecycle. It loads the registry, calls the selected provider planner, validates the returned plan, records tasks, schedules ready work, evaluates results, handles bounded retries and persists the terminal run status.

Specialists are model invocations with bounded roles rather than separate operating-system processes. Each invocation receives its AgentForge role profile, task instructions, relevant skills and references, shared engineering rules, project root and successful dependency outputs.

## Planning and provider boundary

The provider protocol exposes:

- plan(goal, available_agents) -> ExecutionPlan
- execute(AgentRequest) -> AgentResult

Mock produces deterministic demo outputs and never changes project files. OpenAI and Anthropic adapters support model tool-calling for workspace operations. The runtime owns scheduler state, retries, deadlines and persistence.

## Workspace tool capabilities

LLM providers receive a fixed set of tools:

- workspace_list_files
- workspace_read_file
- workspace_search_files
- workspace_write_file (only when the AgentForge role has default_mode read-write)

The workspace root is set through FORGE_WORKSPACE_ROOT and resolved to an absolute directory. Paths are checked after resolution and may not escape the root. Traversal, drive-qualified paths, excluded build/dependency directories, secret environment files and private-key files are blocked. Read/write sizes, search results, tool rounds and total tool calls are capped.

There is no shell command, process execution, network, deletion, Git push, deployment or arbitrary MCP tool. Model providers cannot execute tests in this version; they must report validation that remains to be run.

## DAG scheduler

A plan is a directed acyclic graph. Validation rejects duplicate IDs, unknown roles/skills, missing dependencies, self-dependencies, cycles, plans larger than 100 tasks and tasks requiring human approval while approval gates are unavailable.

Tasks are eligible only when all dependencies succeeded. Independent tasks run concurrently up to the configured semaphore. Successful outputs flow to downstream tasks. Failed tasks are retried within their configured attempt limit; dependents of failed work become blocked.

## State and event log

SQLite stores run snapshots, task statuses, output and audit events. It is appropriate for local/single-process use. It is not a distributed queue or multi-tenant production database.

## HTTP API

The optional FastAPI service exposes health, registry inspection, synchronous run submission and run history endpoints. It binds to localhost by default. Network binds require FORGE_API_TOKEN and X-Forge-API-Key. A run request waits for execution to finish.

## Future production architecture

A production deployment should add PostgreSQL, durable workers, worker leases, cancellation and idempotency, an artifact store, sandboxed command execution, a resumable approval service, tenant authorization, cost budgets and event streaming.
