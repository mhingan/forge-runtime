# Roadmap

## Runtime foundation
- [x] Python package structure and typed execution contracts
- [x] Published AgentForge Toolkit 1.1.0 dependency
- [x] Read packaged AgentForge catalog via agentforge.core.data_root()
- [x] Local checkout and GitHub source adapters
- [x] Map catalog role modes and recommended skills
- [x] Load role profiles, skills, linked references, rules and workflows
- [x] Mock, OpenAI and Anthropic provider adapters
- [x] DAG validation and bounded concurrent task scheduling
- [x] Retries, deadlines and failed-dependency propagation
- [x] SQLite run/task/event persistence
- [x] CLI and optional local FastAPI control API
- [x] Role-based workspace list/read/search/write tools for LLM providers
- [x] Docker sandbox command tool with offline containers and resource limits
- [x] Sanitized workspace snapshots with read-only/read-write result handling
- [x] Sandbox CLI, bundled image, configuration and security tests
- [x] Forge MCP registry dependency and enabled-connection tool bridge for OpenAI/Anthropic agents
- [x] Forge CLI forwarding for MCP discovery, credentials, and local gateway commands
- [x] VS Code Copilot setup for Forge Runner and the single local MCP gateway
- [x] Registry, graph, scheduler, API, workspace, sandbox and storage test coverage

## Production orchestration
- [ ] Strict JSON Schema-constrained planning and bounded plan repair
- [ ] Human approval state machine and resumable approval endpoints
- [ ] PostgreSQL repository and schema migrations
- [ ] Durable worker queue, leases, cancellation and idempotency
- [ ] Usage/token cost tracking, budgets and per-project quotas
- [ ] Semantic evaluation and reviewer-agent quality gates
- [ ] Global concurrency limits and provider rate-limit backoff

## Execution plane
- [ ] OAuth provider compatibility tests against representative remote MCP servers
- [ ] Per-tool MCP approvals for destructive or externally visible actions
- [ ] MCP connection health checks and long-lived connection pooling
- [ ] VM/microVM isolation for hostile multi-tenant workloads
- [ ] Task-level capability manifests and human approval for destructive actions
- [ ] Git worktree isolation and patch-based code integration
- [ ] Human-reviewed artifact promotion
- [ ] Artifact store, checksums and provenance

## Operator experience
- [ ] Web dashboard and streamed task event timeline
- [ ] Provider traces, latency metrics and cost reporting
- [ ] Evaluation datasets and regression benchmarks
- [ ] Project profiles and multi-tenant administration
