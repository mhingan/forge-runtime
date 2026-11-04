"""Ephemeral Docker-based command execution for agent tasks.

Commands run in a disposable, offline, unprivileged container against a sanitized
workspace snapshot. Only changed regular files are copied back, and only for
AgentForge roles with read-write permission.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from forge_runtime.workspace import WorkspaceError, WorkspaceTools


class SandboxError(RuntimeError):
    """Docker sandbox configuration or execution failed."""


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    output_truncated: bool = False
    changed_files: list[str] | None = None
    applied_files: list[str] | None = None
    changes_discarded: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["changed_files"] = self.changed_files or []
        data["applied_files"] = self.applied_files or []
        return data


class DockerSandboxExecutor:
    """Run allowlisted developer commands in a locked-down Docker container."""

    ALLOWED_COMMANDS = {
        "bash", "sh", "python", "python3", "pytest", "ruff", "mypy", "coverage",
        "tox", "nox", "uv", "pip", "pip3", "npm", "npx", "node", "git",
        "make", "cmake", "gcc", "g++", "clang", "go", "cargo", "rustc",
        "java", "javac", "mvn", "gradle", "php", "composer", "ruby", "bundle",
        "rspec", "dart", "flutter",
    }
    MAX_ARGS = 64
    MAX_ARGUMENT_CHARS = 16_000
    DEFAULT_TIMEOUT_SECONDS = 180
    MAX_TIMEOUT_SECONDS = 600
    DEFAULT_OUTPUT_CHARS = 24_000
    MAX_SNAPSHOT_FILES = 5_000
    MAX_SNAPSHOT_BYTES = 512 * 1024 * 1024
    MAX_SINGLE_FILE_BYTES = 32 * 1024 * 1024
    SENSITIVE_NAMES = WorkspaceTools.SENSITIVE_FILE_NAMES
    SENSITIVE_SUFFIXES = WorkspaceTools.SENSITIVE_SUFFIXES
    EXCLUDED_DIRS = WorkspaceTools.EXCLUDED_DIRS
    IGNORED_FILES = {
        ".coverage", "coverage.xml", ".DS_Store", "npm-debug.log",
        "yarn-error.log", "pnpm-debug.log",
    }

    def __init__(
        self,
        workspace_root: Path | str = ".",
        *,
        image: str = "forge-runtime-sandbox:latest",
        docker_binary: str = "docker",
        cpu_limit: float = 2.0,
        memory_mb: int = 2048,
        pids_limit: int = 128,
        default_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_timeout_seconds: int = MAX_TIMEOUT_SECONDS,
        output_chars: int = DEFAULT_OUTPUT_CHARS,
        max_snapshot_files: int = MAX_SNAPSHOT_FILES,
        max_snapshot_bytes: int = MAX_SNAPSHOT_BYTES,
    ) -> None:
        self.workspace = WorkspaceTools(workspace_root)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", image):
            raise SandboxError("Sandbox image name contains unsupported characters.")
        if not docker_binary or any(char.isspace() for char in docker_binary):
            raise SandboxError("Docker binary must be a single executable name or path.")
        if not 0.25 <= cpu_limit <= 16:
            raise SandboxError("Sandbox CPU limit must be between 0.25 and 16.")
        if not 256 <= memory_mb <= 32768:
            raise SandboxError("Sandbox memory limit must be between 256 and 32768 MB.")
        if not 32 <= pids_limit <= 2048:
            raise SandboxError("Sandbox PID limit must be between 32 and 2048.")
        if not 1 <= default_timeout_seconds <= max_timeout_seconds <= self.MAX_TIMEOUT_SECONDS:
            raise SandboxError(
                f"Sandbox timeouts must be between 1 and {self.MAX_TIMEOUT_SECONDS} seconds."
            )
        if not 1_000 <= output_chars <= 100_000:
            raise SandboxError("Sandbox output limit must be between 1000 and 100000 characters.")
        if max_snapshot_files < 1 or max_snapshot_bytes < 1:
            raise SandboxError("Sandbox snapshot limits must be positive.")
        self.image = image
        self.docker_binary = docker_binary
        self.cpu_limit = cpu_limit
        self.memory_mb = memory_mb
        self.pids_limit = pids_limit
        self.default_timeout_seconds = default_timeout_seconds
        self.max_timeout_seconds = max_timeout_seconds
        self.output_chars = output_chars
        self.max_snapshot_files = max_snapshot_files
        self.max_snapshot_bytes = max_snapshot_bytes

    @staticmethod
    def _relative(path: Path, root: Path) -> str:
        return path.relative_to(root).as_posix()

    def _is_excluded(self, relative: Path) -> bool:
        parts = tuple(part.lower() for part in relative.parts)
        if any(part in self.EXCLUDED_DIRS for part in parts):
            return True
        if not parts:
            return False
        filename = parts[-1]
        if filename in self.SENSITIVE_NAMES or filename in self.IGNORED_FILES:
            return True
        if filename.startswith(".env.") and filename != ".env.example":
            return True
        if Path(filename).suffix.lower() in self.SENSITIVE_SUFFIXES:
            return True
        return False

    def _copy_workspace(self, destination: Path) -> dict[str, str]:
        """Copy safe regular files and return their content-hash manifest."""
        root = self.workspace.root
        manifest: dict[str, str] = {}
        total_bytes = 0
        for base, dirs, files in os.walk(root, followlinks=False):
            base_path = Path(base)
            relative_dir = base_path.relative_to(root)
            dirs[:] = [
                name for name in dirs
                if not (base_path / name).is_symlink()
                and not self._is_excluded(relative_dir / name)
            ]
            target_dir = destination / relative_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            for filename in files:
                source = base_path / filename
                relative_file = relative_dir / filename
                if source.is_symlink() or self._is_excluded(relative_file):
                    continue
                try:
                    file_size = source.stat().st_size
                except OSError:
                    continue
                if file_size > self.MAX_SINGLE_FILE_BYTES:
                    raise SandboxError(
                        f"Workspace file {relative_file.as_posix()} exceeds the "
                        f"{self.MAX_SINGLE_FILE_BYTES // (1024 * 1024)} MB snapshot limit."
                    )
                total_bytes += file_size
                if len(manifest) >= self.max_snapshot_files:
                    raise SandboxError(
                        f"Workspace snapshot exceeds {self.max_snapshot_files} files."
                    )
                if total_bytes > self.max_snapshot_bytes:
                    raise SandboxError(
                        "Workspace snapshot exceeds "
                        f"{self.max_snapshot_bytes // (1024 * 1024)} MB."
                    )
                target = destination / relative_file
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                try:
                    with source.open("rb") as reader, target.open("wb") as writer:
                        while chunk := reader.read(1024 * 1024):
                            digest.update(chunk)
                            writer.write(chunk)
                    source_mode = stat.S_IMODE(source.stat().st_mode)
                    target.chmod(source_mode & 0o755)
                except OSError as exc:
                    raise SandboxError(f"Could not snapshot {relative_file}: {exc}") from exc
                manifest[relative_file.as_posix()] = digest.hexdigest()
        return manifest

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _collect_changes(
        self,
        snapshot: Path,
        baseline: dict[str, str],
    ) -> tuple[list[str], list[str]]:
        changed: list[str] = []
        deleted: list[str] = []
        seen: set[str] = set()
        for base, dirs, files in os.walk(snapshot, followlinks=False):
            base_path = Path(base)
            relative_dir = base_path.relative_to(snapshot)
            dirs[:] = [
                name for name in dirs
                if not (base_path / name).is_symlink()
                and not self._is_excluded(relative_dir / name)
            ]
            for filename in files:
                item = base_path / filename
                relative = relative_dir / filename
                key = relative.as_posix()
                if item.is_symlink() or self._is_excluded(relative):
                    continue
                try:
                    size = item.stat().st_size
                except OSError:
                    continue
                if size > self.MAX_SINGLE_FILE_BYTES:
                    continue
                seen.add(key)
                current_hash = self._hash_file(item)
                if baseline.get(key) != current_hash:
                    changed.append(key)
        for key in baseline:
            if key not in seen:
                deleted.append(key)
        return sorted(changed), sorted(deleted)

    def _safe_destination(self, relative_value: str) -> Path:
        relative = PurePosixPath(relative_value)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise SandboxError(f"Sandbox produced an unsafe output path: {relative_value}")
        if self._is_excluded(Path(*relative.parts)):
            raise SandboxError(f"Sandbox output path is protected: {relative_value}")
        current = self.workspace.root
        for part in relative.parts[:-1]:
            candidate = current / part
            if candidate.is_symlink():
                raise SandboxError(f"Sandbox output parent is a symlink: {relative_value}")
            if candidate.exists() and not candidate.is_dir():
                raise SandboxError(f"Sandbox output parent is not a directory: {relative_value}")
            if not candidate.exists():
                candidate.mkdir()
            current = candidate
        parent = current
        try:
            parent.resolve().relative_to(self.workspace.root)
        except ValueError as exc:
            raise SandboxError(f"Sandbox output escapes workspace: {relative_value}") from exc
        target = parent / relative.name
        if target.is_symlink():
            raise SandboxError(f"Refusing to replace workspace symlink: {relative_value}")
        return target

    def _apply_changes(self, snapshot: Path, changed: list[str]) -> list[str]:
        applied: list[str] = []
        for relative in changed:
            source = snapshot / Path(*PurePosixPath(relative).parts)
            if source.is_symlink() or not source.is_file():
                continue
            target = self._safe_destination(relative)
            data_size = source.stat().st_size
            if data_size > self.MAX_SINGLE_FILE_BYTES:
                continue
            temporary_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb", prefix=".forge-sandbox-", dir=target.parent, delete=False
                ) as temporary, source.open("rb") as reader:
                    shutil.copyfileobj(reader, temporary)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                    temporary_name = temporary.name
                os.replace(temporary_name, target)
                source_mode = stat.S_IMODE(source.stat().st_mode)
                target.chmod(source_mode & 0o755)
                applied.append(relative)
            except OSError as exc:
                raise SandboxError(f"Could not apply sandbox output {relative}: {exc}") from exc
            finally:
                if temporary_name and os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        return applied

    @staticmethod
    def validate_argv(argv: Any) -> list[str]:
        if not isinstance(argv, list) or not argv or len(argv) > DockerSandboxExecutor.MAX_ARGS:
            raise SandboxError("argv must be a non-empty array with at most 64 strings.")
        if any(not isinstance(item, str) or not item or "\x00" in item for item in argv):
            raise SandboxError("Every command argument must be a non-empty string.")
        if sum(len(item) for item in argv) > DockerSandboxExecutor.MAX_ARGUMENT_CHARS:
            raise SandboxError("Command arguments exceed the 16000-character limit.")
        executable = argv[0]
        if executable not in DockerSandboxExecutor.ALLOWED_COMMANDS:
            allowed = ", ".join(sorted(DockerSandboxExecutor.ALLOWED_COMMANDS))
            raise SandboxError(
                f"Command '{executable}' is not allowed. Available executables: {allowed}."
            )
        return argv

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "workspace_run_command",
                "description": (
                    "Run a developer/test command in an ephemeral Docker sandbox. "
                    "Network is disabled, the filesystem is isolated to a sanitized project "
                    "snapshot, and CPU/memory/process/time limits are enforced. Use argv as "
                    "an array (not a shell command string). Changes are copied back only for "
                    "read-write roles. Common commands: python -m pytest, pytest, ruff check ., "
                    "npm test, node --test, git diff."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "argv": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": self.MAX_ARGS,
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": self.max_timeout_seconds,
                            "default": self.default_timeout_seconds,
                        },
                    },
                    "required": ["argv"],
                    "additionalProperties": False,
                },
            }
        ]

    def _docker_args(self, snapshot: Path, *, container_name: str) -> list[str]:
        uid = os.getuid() if hasattr(os, "getuid") else 10001
        gid = os.getgid() if hasattr(os, "getgid") else 10001
        if uid == 0:
            uid, gid = 10001, 10001
            if hasattr(os, "chown"):
                for base, dirs, files in os.walk(snapshot):
                    os.chown(base, uid, gid)
                    for name in files:
                        try:
                            os.chown(Path(base) / name, uid, gid, follow_symlinks=False)
                        except OSError:
                            pass

        args = [
            "run", "--rm", "--name", container_name,
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids_limit),
            "--memory", f"{self.memory_mb}m",
            "--cpus", str(self.cpu_limit),
            "--shm-size", "64m",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
            "--user", f"{uid}:{gid}",
            "--workdir", "/workspace",
            "--env", "HOME=/tmp",
            "--env", "TMPDIR=/tmp",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "PYTEST_ADDOPTS=-p no:cacheprovider",
            "--mount", f"type=bind,src={snapshot},dst=/workspace",
        ]
        dependencies = self.workspace.root / "node_modules"
        if dependencies.is_dir() and not dependencies.is_symlink():
            args.extend([
                "--mount",
                f"type=bind,src={dependencies.resolve()},dst=/workspace/node_modules,readonly",
            ])
        args.append(self.image)
        return args

    async def _read_limited(self, stream: asyncio.StreamReader) -> tuple[bytes, bool]:
        maximum = self.output_chars * 4
        output = bytearray()
        truncated = False
        while chunk := await stream.read(64 * 1024):
            available = maximum - len(output)
            if available > 0:
                output.extend(chunk[:available])
            if len(chunk) > available:
                truncated = True
        return bytes(output), truncated

    async def _run_container(
        self,
        snapshot: Path,
        argv: list[str],
        timeout_seconds: int,
    ) -> tuple[int, str, str, bool, bool]:
        container_name = f"forge-task-{uuid.uuid4().hex[:16]}"
        args = [self.docker_binary, *self._docker_args(snapshot, container_name=container_name), *argv]
        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise SandboxError(
                "Docker CLI was not found. Install Docker Desktop/Engine and ensure "
                f"'{self.docker_binary}' is on PATH."
            ) from exc
        except OSError as exc:
            raise SandboxError(f"Could not start Docker: {exc}") from exc

        assert process.stdout is not None
        assert process.stderr is not None
        stdout_task = asyncio.create_task(self._read_limited(process.stdout))
        stderr_task = asyncio.create_task(self._read_limited(process.stderr))
        timed_out = False
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
        except TimeoutError:
            timed_out = True
            await self._stop_container(container_name)
            if process.returncode is None:
                process.kill()
            await process.wait()
        stdout_data, stdout_truncated = await stdout_task
        stderr_data, stderr_truncated = await stderr_task
        if timed_out:
            stderr_data += b"\nForge Runtime: command timed out and the sandbox was stopped."
        return (
            process.returncode if process.returncode is not None else 124,
            stdout_data.decode("utf-8", errors="replace"),
            stderr_data.decode("utf-8", errors="replace"),
            timed_out,
            stdout_truncated or stderr_truncated,
        )

    async def _stop_container(self, name: str) -> None:
        for action in ("kill", "rm"):
            command = [self.docker_binary, action]
            if action == "rm":
                command.append("-f")
            command.append(name)
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(process.wait(), timeout=5)
            except (OSError, TimeoutError):
                continue

    async def run(
        self,
        argv: Any,
        *,
        writable: bool,
        timeout_seconds: int | None = None,
    ) -> SandboxResult:
        command = self.validate_argv(argv)
        timeout = timeout_seconds or self.default_timeout_seconds
        if not isinstance(timeout, int) or not 1 <= timeout <= self.max_timeout_seconds:
            raise SandboxError(
                f"timeout_seconds must be between 1 and {self.max_timeout_seconds}."
            )

        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="forge-sandbox-") as temporary:
            snapshot = Path(temporary) / "workspace"
            snapshot.mkdir()
            baseline = self._copy_workspace(snapshot)
            exit_code, stdout, stderr, timed_out, truncated = await self._run_container(
                snapshot, command, timeout
            )
            changed, deleted = self._collect_changes(snapshot, baseline)
            applied = self._apply_changes(snapshot, changed) if writable else []
            if deleted:
                stderr += (
                    "\nForge Runtime: deletions are not copied back "
                    f"({len(deleted)} file(s) left untouched)."
                )
            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=round(time.monotonic() - started, 3),
                timed_out=timed_out,
                output_truncated=truncated,
                changed_files=changed,
                applied_files=applied,
                changes_discarded=bool(changed) and not writable,
            )

    async def execute_tool(
        self,
        arguments: dict[str, Any],
        *,
        writable: bool,
    ) -> str:
        try:
            result = await self.run(
                arguments.get("argv"),
                writable=writable,
                timeout_seconds=arguments.get("timeout_seconds"),
            )
            data = result.as_dict()
            data["status"] = (
                "timed_out" if result.timed_out
                else "succeeded" if result.exit_code == 0
                else "failed"
            )
            if result.changes_discarded:
                data["note"] = "Role is read-only; sandbox changes were discarded."
            elif result.applied_files:
                data["note"] = "Changed files were copied back to the project workspace."
            return json.dumps(data, ensure_ascii=False)
        except (SandboxError, WorkspaceError) as exc:
            return f"Sandbox error: {exc}"

    async def check(self) -> dict[str, Any]:
        """Check Docker Engine connectivity and whether the configured image exists."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker_binary, "info", "--format", "{{.ServerVersion}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise SandboxError("Docker CLI was not found on PATH.") from exc
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise SandboxError(f"Docker Engine is unavailable: {detail}")
        version = stdout.decode("utf-8", errors="replace").strip()
        image_process = await asyncio.create_subprocess_exec(
            self.docker_binary, "image", "inspect", self.image,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(image_process.wait(), timeout=15)
        return {
            "docker_server_version": version,
            "image": self.image,
            "image_available": image_process.returncode == 0,
            "workspace": str(self.workspace.root),
        }

    async def build_image(self, dockerfile: Path | None = None) -> str:
        """Build the bundled, trusted toolchain image."""
        bundled = Path(__file__).resolve().parent / "sandbox_assets" / "Dockerfile"
        dockerfile = dockerfile or bundled
        if not dockerfile.is_file():
            raise SandboxError(f"Sandbox Dockerfile was not found: {dockerfile}")
        command = [
            self.docker_binary,
            "build",
            "--pull",
            "--tag",
            self.image,
            "--file",
            str(dockerfile),
            str(dockerfile.parent),
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as exc:
            raise SandboxError("Docker CLI was not found on PATH.") from exc
        output, _ = await asyncio.wait_for(
            process.communicate(), timeout=30 * 60
        )
        text = output.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise SandboxError(text[-self.output_chars * 2 :])
        return text[-self.output_chars * 2 :]
