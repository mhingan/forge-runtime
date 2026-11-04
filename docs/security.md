# Security model

User goals, AgentForge profiles, skills, reference files, workflow playbooks, model output and dependency results are untrusted data.

## Implemented controls

- Registry Markdown is read, never executed.
- Registry paths are constrained to their selected source root.
- Plans are checked against known agent/skill catalogs before dispatch.
- Duplicate task IDs, unknown references, missing dependencies, cycles and plans over 100 tasks are rejected.
- Tasks requiring human approval are rejected because no approval state machine is enabled.
- Concurrency, attempts, task timeouts and output lengths are bounded.
- Workspace tools are confined to FORGE_WORKSPACE_ROOT.
- Absolute paths, traversal and drive-qualified paths are rejected.
- Workspace tools exclude dependency/build directories and block secret environment/private-key writes.
- AgentForge read-only roles do not receive the file-write tool.
- Tool-call rounds, total tool calls, file sizes and search results are capped.
- No shell, command execution, network, delete, deployment or arbitrary MCP tool is enabled.
- HTTP API binds to localhost by default; network binds require an API token.

## Workspace permission model

The runtime maps the AgentForge catalog's default_mode field to tool access:
- read-only: list, read and search tools.
- read-write: list, read, search and file-write tools.

This is a role-level capability boundary, not a complete security sandbox. Agent profile instructions and model responses remain untrusted. A model with read-write permission can overwrite ordinary project text files inside the configured workspace. Review changes with version control before accepting them.

## Not implemented

There is no shell/process executor, test runner, deletion tool, Git commit/push, browser, deployment or arbitrary MCP integration. Model outputs must never claim these actions were performed. The baseline evaluator checks output presence and size; it is not proof of semantic correctness or security.

## Required before production tool execution

1. Add ephemeral container/VM isolation for command execution.
2. Add task-level capability manifests and approval for destructive or externally visible actions.
3. Add authentication and tenant authorization for every run, task and artifact.
4. Encrypt sensitive artifacts and define retention/deletion controls.
5. Test prompt injection at registry, planner, hand-off and tool-result boundaries.
6. Add tool provenance, audit log redaction, quotas, rate limits and provider cost budgets.
