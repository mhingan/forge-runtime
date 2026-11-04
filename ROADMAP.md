# Roadmap

## Runtime foundation
- [x] Python package structure and typed execution contracts
- [x] Published AgentForge Toolkit 1.1.0 dependency
- [x] Read packaged AgentForge catalog via agentforge.core.data_root()
- [x] Local checkout and GitHub source adapters
- [x] Map catalog role modes and recommended skills
- [x] Load engineering rules and workflow Markdown
- [x] Mock, OpenAI and Anthropic provider interfaces
- [x] DAG validation and bounded concurrent task scheduling
- [x] Retries, deadlines, blocked dependency propagation
- [x] SQLite run, task and event persistence
- [x] CLI for registry, roles, skills, rules, workflows and runs
- [x] Optional local FastAPI control API
- [x] Baseline registry, graph, scheduler and storage tests

## Production orchestration
- [ ] Strict JSON Schema-constrained planner responses and bounded plan repair
- [ ] Human approval state machine and resume endpoint
- [ ] PostgreSQL repository and schema migrations
- [ ] Durable worker queue, leases, cancellation and idempotency
- [ ] Usage/token cost tracking, budgets and per-project quotas
- [ ] Semantic evaluation and reviewer-agent quality gates
- [ ] Run concurrency limits and provider rate-limit backoff

## Tool execution
- [ ] Capability-scoped tool registry and execution contracts
- [ ] Ephemeral container/VM sandbox for shell and file operations
- [ ] Git worktree isolation and patch-based code integration
- [ ] Human-reviewed artifact promotion
- [ ] Artifact store, checksums and provenance

## Operator experience
- [ ] Web dashboard and streamed task event timeline
- [ ] Provider traces, latency metrics and cost reporting
- [ ] Evaluation datasets and regression benchmarks
- [ ] Project profiles and multi-tenant administration
