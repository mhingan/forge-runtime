# Docker sandbox executor

## Why a separate executor exists

LLM providers need a way to run tests, linters and project build commands after editing code. Executing those commands directly on the Forge Runtime host would grant the agent the host user's permissions. Forge Runtime instead creates a disposable Docker container for each command and mounts only a sanitized project snapshot.

This is a Docker container boundary, not a VM. Use it on a trusted, patched Docker host. Container isolation cannot protect against Docker daemon compromise, container escape vulnerabilities or malicious code that exploits the host kernel.

## Setup

Install and start Docker Desktop or Docker Engine. Then, from the Forge Runtime environment:

```bash
forge sandbox check
forge sandbox build
forge sandbox check
```

The bundled image is `forge-runtime-sandbox:latest`. It contains Python 3.12, pytest, Ruff, mypy, coverage, uv, Node.js/npm, Git, bash, make and common build tools. The image build uses network access to download its base image and packages. Runtime agent containers do not have network access.

To use a custom toolchain, edit `src/forge_runtime/sandbox_assets/Dockerfile`, rebuild with `forge sandbox build`, and update `FORGE_SANDBOX_IMAGE` if you choose a different tag.

## Manual smoke tests

```bash
forge sandbox run -- python --version
forge sandbox run -- pytest --version
forge sandbox run -- python -m pytest
forge sandbox run -- ruff check .
forge sandbox run -- npm test
```

Use `--read-write` only for an explicit local run where changes should be copied back:

```bash
forge sandbox run --read-write -- ruff check . --fix
```

The CLI is a diagnostic interface. In normal agent runs, OpenAI and Anthropic tool-calling invokes the same executor through `workspace_run_command`.

## Container security profile

Each command is run in a newly named, disposable container:

- `--network none`; runtime image pulls are disabled with `--pull=never`.
- Container root filesystem is read-only.
- Linux capabilities are dropped; `no-new-privileges` is enabled.
- Container runs with a non-root numeric UID/GID.
- CPU, memory, PID count, shared memory, command duration and captured output are bounded.
- `/tmp` is a bounded tmpfs.
- No Docker socket, host credentials, host environment variables or arbitrary host paths are mounted.
- Only the sanitized project snapshot is mounted read/write. Existing `node_modules`, when present, is mounted separately as read-only.

The host Docker daemon is still a privileged component. The container boundary does not provide a VM-grade security guarantee.

## Project snapshot rules

Before each command, Forge Runtime copies regular files into a temporary directory. It excludes:

- `.git`, virtual environments, `node_modules`, build outputs and common caches.
- `.env` files other than the safe `.env.example` template.
- Credential/config files such as `.npmrc`, `.pypirc`, `.netrc`, credentials JSON and private keys.
- Sensitive directories including `.ssh`, `.aws`, `.secrets` and `.terraform`.
- Symbolic links and files larger than the configured per-file limit.

Snapshot file count and total bytes are bounded. A project larger than those limits fails before a container starts.

### Applying changes

The executor hashes the snapshot before running the command and compares hashes afterward. For a `read-write` AgentForge role, new or modified regular files are applied atomically to the host workspace after path and symlink checks. For a `read-only` role, all changes are discarded.

Deletions, symlinks, sensitive files and excluded paths are never copied back. Changes made by a command that exits non-zero are still copied back for read-write roles; this allows formatters/build steps and partial fixes to be inspected, but means failed commands can leave modified project files. Review the Git diff after every agent run.

## Tool contract

LLM agents receive `workspace_run_command` with this shape:

```json
{
  "argv": ["python", "-m", "pytest"],
  "timeout_seconds": 180
}
```

The executable must be on the built-in allowlist. Arguments are passed directly to Docker as an argv array; no host shell parses the command. `bash` and `sh` are allowed inside the container for project scripts. The sandbox tool returns exit code, stdout, stderr, elapsed time, timeout status, changed files and applied files.

The runtime caps tool-call rounds at the provider layer and the sandbox caps command duration, output, file count and snapshot size.

## Configuration

All settings use the `FORGE_` prefix and are shown in `.env.example`.

| Setting | Default | Description |
|---|---:|---|
| `FORGE_SANDBOX_ENABLED` | `true` | Expose command execution to LLM providers |
| `FORGE_SANDBOX_IMAGE` | `forge-runtime-sandbox:latest` | Already-built local image |
| `FORGE_SANDBOX_DOCKER_BINARY` | `docker` | Docker CLI path/name |
| `FORGE_SANDBOX_CPU_LIMIT` | `2` | CPUs per container |
| `FORGE_SANDBOX_MEMORY_MB` | `2048` | Memory limit |
| `FORGE_SANDBOX_PIDS_LIMIT` | `128` | PID/process limit |
| `FORGE_SANDBOX_DEFAULT_TIMEOUT_SECONDS` | `180` | Default command timeout |
| `FORGE_SANDBOX_MAX_TIMEOUT_SECONDS` | `600` | Maximum requested timeout |
| `FORGE_SANDBOX_OUTPUT_CHARS` | `24000` | Captured stdout/stderr limit |
| `FORGE_SANDBOX_MAX_SNAPSHOT_FILES` | `5000` | Maximum copied project files |
| `FORGE_SANDBOX_MAX_SNAPSHOT_MB` | `512` | Maximum snapshot size |

Set `FORGE_SANDBOX_ENABLED=false` to hide the command tool from model providers. The CLI diagnostic commands remain available.

## Limitations

- Network access is disabled during agent commands. Dependency installation from PyPI/npm or remote Git hosts will fail unless dependencies are already in the image or present in the read-only `node_modules` mount.
- The default image includes a common Python/Node toolchain, not every language SDK. Add project-specific dependencies to the trusted Dockerfile and rebuild.
- Host Python virtual environments are intentionally excluded because native extensions and absolute interpreter paths are not portable into Linux containers.
- The project `.git` directory is excluded; commands cannot commit or inspect host Git history.
- File deletion and symlink changes are not propagated back.
- There is no automatic test-plan approval gate or deployment integration.
