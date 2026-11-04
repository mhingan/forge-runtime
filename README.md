# Forge Runtime

**A provider-neutral execution and orchestration engine for the AgentForge ecosystem.**

Forge Runtime turns one user goal into a validated multi-agent execution graph. Forge Master selects specialist roles from AgentForge, asks an LLM provider to create a plan, validates the task dependencies, dispatches work concurrently, passes successful dependency results downstream, evaluates task outputs, and persists an execution history.

## AgentForge integration

Forge Runtime depends on the published distribution **agentforge-toolkit 1.1.0**. The toolkit exposes its bundled library directory through `agentforge.core.data_root()`; the runtime reads the catalogs and Markdown definitions from that packaged data.

| Project | Responsibility |
|---|---|
| [AgentForge](https://github.com/mhingan/agent-forge) / [PyPI](https://pypi.org/project/agentforge-toolkit/1.1.0/) | Agent roles, skills, rules, workflows, catalogs, provider-specific coding-agent installation |
| **Forge Runtime** | Forge Master, planning, DAG scheduling, dispatch, model-provider calls, state, evaluation, API and execution reports |

The runtime does not call an undocumented AgentForge registry class or assume the toolkit is a hosted service. The adapter uses the package's real `data_root()` entry point. A local repository checkout and GitHub raw source are also supported.

## Runtime capabilities

- **Forge Master:** central coordinator for each execution run.
- **AgentForge registry:** reads packaged roles, skills, rules and workflow playbooks.
- **Planning:** OpenAI and Anthropic providers produce a structured execution plan; mock provider supports deterministic smoke tests.
- **Task graph:** validates unique IDs, known roles/skills, dependencies, cycles and task limits before dispatch.
- **Parallel scheduler:** independent tasks run concurrently under a configurable semaphore.
- **Dependency context:** successful outputs are passed to tasks that depend on them.
- **Retries and deadlines:** bounded attempts and per-task timeouts.
- **Failure propagation:** tasks that depend on failed work are marked blocked.
- **Evaluation:** baseline output validation behind a replaceable evaluator contract.
- **Persistence:** SQLite records runs, task states, outputs and execution events.
- **CLI and HTTP API:** inspect the registry, submit work and inspect run history.

## Architecture

```text
                 User goal / CLI / HTTP API
                            |
                            v
                    FORGE MASTER
                            |
               Load AgentForge toolkit data
                            |
                 LLM planner / Mock planner
                            |
                  Validate execution DAG
                            |
                     Task scheduler
                 /         |          \
                v          v           v
           Architect    Backend      Product ...
                |          |           |
                +----------+-----------+
                            |
                 Dependency result hand-off
                            |
                   Evaluator / Retry
                            |
                      SQLite store
                            |
                 Run report + event history
```

AgentForge profiles and skills are model context, not executable permissions. This version does not include shell, repository-write, browser, deployment or arbitrary MCP tools. A provider cannot modify the host project through this runtime.

## Requirements

- Python 3.11+
- AgentForge Toolkit 1.1.0 (installed automatically as a project dependency)
- An API key only when using OpenAI or Anthropic

## Install from source

```bash
git clone https://github.com/mhingan/forge-runtime.git
cd forge-runtime
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,openai,api]"
cp .env.example .env
```

The dependency installation also installs `agentforge-toolkit==1.1.0`. No separate AgentForge clone is required for the standard configuration.

## First run — mock provider

```bash
forge registry validate
forge agent list
forge skill list
forge rule list
forge workflow list

forge run "Design a secure REST API for an e-commerce platform" --provider mock
forge runs list
```

Mock mode verifies registry loading, planning, graph validation, scheduling, persistence and event creation without making model API calls. Its outputs are clearly marked as demonstrations; it does not produce real code changes.

## Run with an LLM

For OpenAI:

```bash
export OPENAI_API_KEY="..."
export FORGE_DEFAULT_PROVIDER=openai
forge run "Build a secure customer management API with tests"
```

Or choose a provider per run:

```bash
forge run "Review the backend architecture" --provider openai
forge run "Plan a Flutter application" --provider anthropic
```

Optional provider installs:

```bash
python -m pip install -e ".[openai]"
python -m pip install -e ".[anthropic]"
```

The LLM providers plan and generate task outputs, but they do not have host tools. They must not claim to have modified files, run tests or deployed software.

## Registry source selection

The default setting `FORGE_AGENTFORGE_SOURCE=auto` loads the packaged AgentForge data via `agentforge.core.data_root()`.

| Setting | Behavior |
|---|---|
| `auto` | Use installed toolkit; fall back to GitHub when it is unavailable |
| `installed` | Require installed `agentforge-toolkit` package data |
| `local` | Use `FORGE_AGENTFORGE_LOCAL_PATH` |
| `github` | Fetch catalogs and referenced Markdown from the configured GitHub ref |

For a local AgentForge checkout:

```bash
export FORGE_AGENTFORGE_SOURCE=local
export FORGE_AGENTFORGE_LOCAL_PATH="../agent-forge"
forge registry validate
```

## Local HTTP API

Install the API extra and start the service:

```bash
python -m pip install -e ".[api]"
forge serve
```

Default address: `http://127.0.0.1:8787`. Interactive API documentation is available at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health |
| GET | `/v1/agents` | AgentForge agent catalog |
| GET | `/v1/skills` | AgentForge skill catalog |
| POST | `/v1/runs` | Submit a goal and execute the run |
| GET | `/v1/runs` | List recent runs |
| GET | `/v1/runs/{run_id}` | Read run, task and event records |

Example:

```bash
curl http://127.0.0.1:8787/v1/agents

curl -X POST http://127.0.0.1:8787/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"goal":"Plan a secure inventory API","provider":"mock"}'
```

The API executes a submitted run synchronously and returns the final run record. This is a local control API, not yet a durable background job service. Keep it bound to localhost for personal development. For a network bind, set a strong `FORGE_API_TOKEN`; send it as `X-Forge-API-Key`.

## Configuration

See `.env.example`.

| Variable | Purpose | Default |
|---|---|---|
| `FORGE_DEFAULT_PROVIDER` | Default model provider | `mock` |
| `FORGE_MAX_PARALLEL_TASKS` | Max concurrent tasks | `4` |
| `FORGE_TASK_TIMEOUT_SECONDS` | Per-task timeout ceiling | `900` |
| `FORGE_DATABASE_URL` | SQLite database URL | `sqlite:///./.forge/forge.db` |
| `FORGE_AGENTFORGE_SOURCE` | Registry source selection | `auto` |
| `OPENAI_API_KEY` | OpenAI key | unset |
| `ANTHROPIC_API_KEY` | Anthropic key | unset |
| `FORGE_API_TOKEN` | HTTP API key for network binds | unset |

## Security and limitations

- All user goals, registry files and model outputs are treated as untrusted content.
- Plans are validated against installed AgentForge role and skill names before any task runs.
- The scheduler enforces bounded concurrency, retries and timeouts.
- No host command execution, filesystem mutation, git write, deployment or MCP tool is available.
- Tasks flagged as requiring human approval are rejected because the approval subsystem is not enabled yet.
- SQLite is intended for local and single-process use; it is not a distributed job queue.
- The baseline evaluator checks output presence and size; it is not a semantic correctness guarantee.
- The HTTP API should not be exposed publicly without a hardened deployment, authentication, TLS and tenant isolation.

## Development

```bash
python -m pip install -e ".[dev,api]"
pytest
ruff check .
```

See [architecture](docs/architecture.md), [provider contracts](docs/providers.md), [security](docs/security.md), [roadmap](ROADMAP.md) and [contributing](CONTRIBUTING.md).

## License

MIT.
