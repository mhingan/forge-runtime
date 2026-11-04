# Forge Runtime

A provider-neutral orchestration runtime for multi-agent systems. Forge Runtime is the execution plane; [AgentForge](https://github.com/mhingan/agent-forge) is the knowledge plane containing specialist roles, skills, rules and workflows.

## Project status

Early-stage foundation. The initial release focuses on typed orchestration contracts, AgentForge repository integration, task graph validation, bounded scheduling, provider abstraction, persistence, CLI inspection and tests. Hosted-model execution is optional. No shell, repository-write, browser, deployment or arbitrary MCP tools are enabled by default.

## Responsibilities

| Repository | Responsibility |
|---|---|
| [agent-forge](https://github.com/mhingan/agent-forge) | Agent definitions, skills, rules, workflows and provider rendering |
| forge-runtime | Forge Master, planning, task DAG, dispatch, provider calls, state, evaluation and events |

The integration reads `catalog/agents.json`, `catalog/skills.json` and referenced Markdown from a local checkout or GitHub raw content. It does not assume AgentForge provides a hosted API or a Python `AgentRegistry` interface.

## Architecture

```text
User request -> Forge Master -> Planner -> Validated task DAG
                                       -> Scheduler -> Dispatcher
                                       -> Specialist agents -> Provider adapters
                                       -> Evaluator -> Retry / approval / completion
                                       -> SQLite state + audit events
```

Core invariants: specialist roles are bounded; dependency graphs must be acyclic; unknown roles/skills are rejected; independent tasks may run concurrently; failed dependencies block descendants; provider output is treated as untrusted; side effects require separately implemented sandboxed tools and explicit approval.

## Roadmap

- [ ] Typed contracts and orchestration core
- [ ] AgentForge registry adapter
- [ ] Mock provider and end-to-end tests
- [ ] SQLite persistence and event timeline
- [ ] Optional OpenAI and Anthropic adapters
- [ ] FastAPI service, authentication and run management
- [ ] PostgreSQL and durable workers
- [ ] Sandboxed tools, approvals and artifact provenance
- [ ] Operator dashboard and streaming events

See `docs/architecture.md`, `docs/security.md`, `docs/providers.md`, `ROADMAP.md` and `CONTRIBUTING.md`.

## License

MIT.
