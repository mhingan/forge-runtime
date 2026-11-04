# Roadmap

## Runtime foundation
- [x] Package structure and typed contracts
- [x] AgentForge local/remote registry adapter
- [x] Provider protocol and deterministic mock
- [x] OpenAI/Anthropic optional adapters
- [x] DAG validation and bounded scheduler
- [x] SQLite run/task/event store
- [x] CLI and baseline regression suite

## Production control plane
- [ ] JSON Schema constrained planning and plan-repair strategy
- [ ] FastAPI run and event API with authentication
- [ ] PostgreSQL repository and migrations
- [ ] Durable dispatch queue, leases, cancellation and idempotency
- [ ] Usage, token-cost budgets, quotas and rate limiting
- [ ] Semantic evaluators and human review gates

## Execution plane
- [ ] Capability manifest and tool registry
- [ ] Ephemeral sandboxed command/file execution
- [ ] Explicit approval service and audit trail
- [ ] Artifact store and provenance
- [ ] Git worktree / patch-based coding agent executor

## Operator experience
- [ ] Live dashboard and streamed event timeline
- [ ] Metrics, traces and provider cost reports
- [ ] Evaluation datasets and regression benchmarks
- [ ] Multi-project and multi-tenant management
