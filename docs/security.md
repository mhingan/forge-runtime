# Security and trust model

All user goals, agent profiles, skills, model responses, dependency outputs and future tool results are untrusted.

## Implemented boundaries
- Markdown registry content is read, not executed.
- Registry roles do not grant runtime permissions.
- No arbitrary shell, filesystem write, repository write, browser, deployment or MCP tools are exposed.
- API credentials are obtained from environment variables.
- Planner outputs are parsed and graph-validated before dispatch.
- Task count, concurrency, attempts, timeouts and output lengths are bounded.

## Before tool execution is enabled
1. Use ephemeral sandboxes with explicit filesystem and network policy.
2. Grant tools per-task capabilities, never broad ambient permissions.
3. Require human approval for destructive, irreversible, production, financial or externally visible effects.
4. Add authentication, tenant isolation, quotas, rate limits and audit retention before a hosted API.
5. Encrypt sensitive artifacts and define retention/deletion controls.
6. Test prompt injection through registry, task hand-off and tool-result contexts.
7. Record provenance for tools, inputs, outputs and approvals.
