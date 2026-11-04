# Architecture

## System boundary

AgentForge is the knowledge plane. The published agentforge-toolkit package embeds canonical specialist profiles, skills, rules, workflow playbooks and catalogs. Forge Runtime is the execution plane: planning, scheduling, delegation, model calls, workspace file operations, sandboxed command execution, evaluation and persisted run state.

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

Mock produces deterministic demo outputs and never changes project files. OpenAI and Anthropic adapters support workspace file tools and Docker sandbox tool-calling. The runtime owns scheduler state, retries, deadlines and persistence.

## Workspace file tools

LLM providers receive list/read/search operations. The write tool is exposed only to AgentForge roles with default_mode read-write. Paths are confined to FORGE_WORKSPACE_ROOT; secrets, credential files and private keys are hidden/protected. Writes use atomic replacement and reject symlinks and path traversal.

## Docker sandbox executor

When FORGE_SANDBOX_ENABLED is true, LLM providers also receive workspace_run_command. The executor:

1. Validates the argv array against a developer-command allowlist and a timeout budget.
2. Copies a sanitized snapshot into a temporary host directory, excluding .git, credentials, dependency/build folders and symlinks.
3. Starts a disposable local image with no network, read-only root filesystem, dropped capabilities, no-new-privileges, numeric non-root UID/GID, CPU/memory/PID/tmpfs limits and command timeout.
4. Mounts only the sanitized snapshot and (when present) node_modules as read-only.
5. Captures bounded stdout/stderr, exit code and elapsed duration.
6. Hashes the snapshot before/after. New/changed regular files are copied back atomically only for read-write roles; deletions and symlinks are discarded.

The image is built explicitly with forge sandbox build. Runtime execution uses --pull=never and does not fetch images. The default image includes Python and Node test/build tools. Project-specific dependencies can be included in a custom trusted Dockerfile. Runtime containers use bridge networking by default, so package installation from remote registries is available. Offline mode is selectable with `FORGE_SANDBOX_NETWORK=none`.

Docker is a container boundary, not a VM. The Docker daemon and host kernel remain trusted components.

## DAG scheduler

A plan is a directed acyclic graph. Validation rejects duplicate IDs, unknown roles/skills, missing dependencies, self-dependencies, cycles, plans larger than 100 tasks and tasks requiring human approval while approval gates are unavailable.

Tasks are eligible only when all dependencies succeeded. Independent tasks run concurrently up to the configured semaphore. Successful outputs flow to downstream tasks. Failed tasks are retried within their configured attempt limit; dependents of failed work become blocked.

## State and event log

SQLite stores run snapshots, task statuses, output and audit events. It is appropriate for local/single-process use. It is not a distributed queue or multi-tenant production database.

## HTTP API

The optional FastAPI service exposes health, registry inspection, synchronous run submission and run history endpoints. It binds to localhost by default. Network clients require FORGE_API_TOKEN and X-Forge-API-Key. A run request waits for execution to finish.

## Future production architecture

A production deployment should add PostgreSQL, durable workers, worker leases, cancellation and idempotency, artifact storage, VM/microVM isolation for hostile code, resumable approval, tenant authorization, cost budgets and event streaming.
