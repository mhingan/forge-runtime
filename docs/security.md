# Security model

User goals, AgentForge profiles, skills, reference files, workflow playbooks, model output, dependency results and project source files are untrusted data.

## Implemented controls

- Registry Markdown is read, never executed.
- Registry paths are constrained to their selected source root.
- Plans are checked against known agent/skill catalogs before dispatch.
- Duplicate task IDs, unknown references, missing dependencies, cycles and plans over 100 tasks are rejected.
- Tasks requiring human approval are rejected because no approval state machine is enabled.
- Concurrency, attempts, task timeouts and output lengths are bounded.
- Workspace tools are confined to FORGE_WORKSPACE_ROOT.
- Secret environment files, credential files, private keys and sensitive credential directories are hidden from listing/search and cannot be read or written by workspace tools.
- The sandbox snapshot excludes .git, credentials, dependency directories, build outputs and symbolic links.
- Sandbox commands run in Docker with bridged internet access by default (or no network when configured), a read-only container root, dropped capabilities, no-new-privileges, a non-root UID, and CPU/memory/PID/time/output limits.
- No host environment variables, host credentials, Docker socket or general host filesystem paths are mounted into command containers.
- Read-only AgentForge roles do not copy sandbox changes back to the project; read-write roles may copy back only new/modified regular files after path and symlink checks.
- Sandbox deletions and symlink changes are not propagated.
- HTTP API binds to localhost by default; non-loopback requests require an API token.
- MCP credentials and OAuth refresh tokens are stored in the operating-system credential store through Forge MCP; there is no plaintext-file fallback.
- MCP connection manifests contain endpoint/command metadata and keyring references only, never credential values.
- Only explicitly enabled MCP servers are exposed to model providers. Remote connections require HTTPS; local STDIO commands execute on the host only after enablement.
- MCP tool descriptions and results are untrusted model context. Tool calls are bounded by the provider's existing round/call budgets; credential values remain inside the connector process.

## Workspace permission model

The runtime maps the AgentForge catalog's default_mode field to tool access:
- read-only: list, read and search tools; sandbox command changes are discarded.
- read-write: list, read, search and file-write tools; sandbox command changes may be copied back.

This is a role-level capability boundary, not an approval or review system. A read-write agent can overwrite ordinary project files and run arbitrary code inside the isolated container. Review changes with version control before accepting them.

## Docker boundary and residual risk

The executor uses a Docker container, not a VM. It shares the host kernel and depends on the Docker daemon and runtime being secure and patched. Container escape vulnerabilities, a compromised daemon, malicious Docker configuration or a hostile host remain outside the protection this runtime can provide. Run Forge Runtime only on a trusted host with Docker access controlled by the operator.

The project snapshot is sanitized, but project code and dependencies can still be malicious. Agent commands can execute that code in the container. With the default Docker bridge network, commands have outbound internet access and may also reach private/LAN addresses routable from the Docker host. The runtime does not implement a domain allowlist or an egress firewall. Use `FORGE_SANDBOX_NETWORK=none` for offline execution or apply host-level egress policy when running untrusted tasks. Internet access also means project data in the snapshot could be sent to external services by code running inside the container.

## Not implemented

There is no Git commit/push, deletion propagation, browser automation, deployment adapter, durable approval state machine or tenant-level authorization for all runtime data. MCP connections are local integrations, not a hosted multi-tenant credential service. The baseline evaluator checks output presence and size; it is not proof of semantic correctness or security.

## Required before production use

1. Add a VM/microVM or stronger per-task isolation for hostile multi-tenant workloads.
2. Add human approval for destructive, irreversible or externally visible actions.
3. Add authenticated tenant authorization for every run, task and artifact.
4. Encrypt sensitive artifacts and define retention/deletion controls.
5. Test prompt injection at registry, planner, hand-off, filesystem and tool-result boundaries.
6. Add tool provenance, audit log redaction, quotas, rate limits and provider cost budgets.
7. Add a per-tool approval state machine for destructive or externally visible MCP operations.
