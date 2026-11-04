# Security model

Forge Runtime coordinates model calls using AgentForge content. A user goal, agent profile, skill, workflow, dependency result or model response can contain hostile or misleading instructions. All such content is untrusted.

## Implemented controls

- Registry Markdown is read as content and never executed.
- Catalog paths are constrained to the registry root; traversal paths are rejected.
- Plans are validated against known roles and skills before dispatch.
- DAG cycles, unknown dependencies, duplicate task IDs and oversized plans are rejected.
- Task count, concurrency, retries, timeouts and output size are bounded.
- Failed dependency chains are blocked.
- Tasks requiring human approval are rejected until the approval mechanism is implemented.
- The HTTP API binds to localhost by default. Network binds require an API token.

## Not implemented

The current runtime does not provide a shell, filesystem-write, repository-write, browser, deployment or arbitrary MCP executor. Provider adapters have no tools. This is deliberate: installing an AgentForge role does not grant it host permissions.

## Required before production tools

1. Use ephemeral sandboxes with explicit filesystem and network policies.
2. Give each executor only task-scoped capabilities and short-lived credentials.
3. Require human approval for destructive, irreversible, financial, production or externally visible effects.
4. Add tenant isolation and authorization to every run, task and artifact endpoint.
5. Encrypt sensitive results; define log redaction, retention and deletion controls.
6. Run prompt-injection tests across registry, planner, hand-off and tool-result boundaries.
7. Record provenance for tool calls, inputs, outputs, approvals and artifacts.
8. Add budgets, quotas, rate limits and abuse protection to network-facing endpoints.
