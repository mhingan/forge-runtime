"""Capability-scoped file tools for LLM coding agents.

All paths are confined to one configured workspace. There is deliberately no shell,
process execution, network access, deletion, or arbitrary MCP execution in this module.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


class WorkspaceError(RuntimeError):
    """A workspace operation is invalid, unavailable, or not authorized."""


class WorkspaceTools:
    EXCLUDED_DIRS = {
        ".git", ".venv", "venv", "node_modules", "__pycache__", ".next",
        ".dart_tool", ".idea", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".forge", "dist", "build", "coverage", "htmlcov",
    }
    MAX_READ_BYTES = 256_000
    MAX_WRITE_BYTES = 256_000
    MAX_SEARCH_FILES = 1_000
    MAX_SEARCH_RESULTS = 40
    MAX_LIST_RESULTS = 250

    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists() or not self.root.is_dir():
            raise WorkspaceError(f"Workspace root is not an existing directory: {self.root}")

    def _resolve(self, value: str, *, allow_root: bool = False) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise WorkspaceError("A non-empty relative workspace path is required.")
        normalized = value.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if pure.is_absolute() or any(part == ".." for part in pure.parts):
            raise WorkspaceError("Absolute paths and '..' traversal are not allowed.")
        if any(part in self.EXCLUDED_DIRS for part in pure.parts):
            raise WorkspaceError("This workspace path is excluded from agent access.")
        if not pure.parts or pure.as_posix() == ".":
            if allow_root:
                return self.root
            raise WorkspaceError("A file path is required.")
        candidate = (self.root / Path(*pure.parts)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("Resolved path escapes the configured workspace.") from exc
        return candidate

    @staticmethod
    def _display(path: Path, root: Path) -> str:
        return path.relative_to(root).as_posix() or "."

    def list_files(self, directory: str = ".") -> str:
        target = self._resolve(directory, allow_root=True)
        if not target.exists() or not target.is_dir():
            raise WorkspaceError(f"Directory does not exist: {directory}")
        entries: list[str] = []
        for path in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            if path.name in self.EXCLUDED_DIRS or path.is_symlink():
                continue
            suffix = "/" if path.is_dir() else ""
            entries.append(self._display(path, self.root) + suffix)
            if len(entries) >= self.MAX_LIST_RESULTS:
                entries.append("... result limit reached")
                break
        return "\n".join(entries) if entries else "(empty directory)"

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        if target.is_symlink() or not target.is_file():
            raise WorkspaceError(f"File does not exist or is not a regular file: {path}")
        size = target.stat().st_size
        if size > self.MAX_READ_BYTES:
            raise WorkspaceError(
                f"File is {size} bytes; maximum supported read is {self.MAX_READ_BYTES} bytes."
            )
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkspaceError("Only UTF-8 text files can be read by this tool.") from exc

    def search_files(self, query: str, directory: str = ".") -> str:
        if not isinstance(query, str) or not query.strip():
            raise WorkspaceError("Search query cannot be empty.")
        target = self._resolve(directory, allow_root=True)
        if not target.exists() or not target.is_dir():
            raise WorkspaceError(f"Directory does not exist: {directory}")
        needle = query.casefold()
        matches: list[str] = []
        scanned = 0
        for base, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [
                name for name in dirs
                if name not in self.EXCLUDED_DIRS and not (Path(base) / name).is_symlink()
            ]
            for filename in files:
                file_path = Path(base) / filename
                if file_path.is_symlink():
                    continue
                scanned += 1
                if scanned > self.MAX_SEARCH_FILES:
                    matches.append("... search file limit reached")
                    return "\n".join(matches) if matches else "No matches."
                try:
                    if file_path.stat().st_size > 512_000:
                        continue
                    text = file_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if needle in line.casefold():
                        matches.append(
                            f"{self._display(file_path, self.root)}:{line_number}: {line[:300]}"
                        )
                        if len(matches) >= self.MAX_SEARCH_RESULTS:
                            matches.append("... result limit reached")
                            return "\n".join(matches)
        return "\n".join(matches) if matches else "No matches."

    def write_file(self, path: str, content: str, *, writable: bool) -> str:
        if not writable:
            raise WorkspaceError(
                "This AgentForge role is read-only. File writes are not permitted."
            )
        target = self._resolve(path)
        if target.is_symlink():
            raise WorkspaceError("Writing through symbolic links is not permitted.")
        name = target.name.lower()
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            raise WorkspaceError("Secret environment files are protected from agent writes.")
        if target.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
            raise WorkspaceError("Private-key and certificate files are protected.")
        if not isinstance(content, str):
            raise WorkspaceError("File content must be text.")
        encoded = content.encode("utf-8")
        if len(encoded) > self.MAX_WRITE_BYTES:
            raise WorkspaceError(
                f"Write is {len(encoded)} bytes; maximum supported write is "
                f"{self.MAX_WRITE_BYTES} bytes."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        # Re-resolve after directory creation to catch symlink swaps in parent paths.
        resolved_parent = target.parent.resolve()
        try:
            resolved_parent.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("Target parent escapes the configured workspace.") from exc
        resolved_target = resolved_parent / target.name
        if resolved_target.exists() and resolved_target.is_symlink():
            raise WorkspaceError("Writing through symbolic links is not permitted.")

        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".forge-write-", dir=resolved_parent, delete=False
            ) as temporary:
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            os.replace(temporary_name, resolved_target)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)

        return (
            f"Wrote {self._display(resolved_target, self.root)} "
            f"({len(encoded)} UTF-8 bytes)."
        )

    def tool_schemas(self, *, writable: bool) -> list[dict[str, Any]]:
        tools = [
            {
                "name": "workspace_list_files",
                "description": "List files and directories inside the assigned project workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"directory": {"type": "string", "default": "."}},
                    "additionalProperties": False,
                },
            },
            {
                "name": "workspace_read_file",
                "description": "Read a UTF-8 text file inside the assigned project workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "workspace_search_files",
                "description": "Search text in project files and return matching lines with paths.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "directory": {"type": "string", "default": "."},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        ]
        if writable:
            tools.append(
                {
                    "name": "workspace_write_file",
                    "description": (
                        "Create or replace a UTF-8 text file inside the project workspace. "
                        "Only use this for files required by the assigned task."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                }
            )
        return tools

    def execute_tool(self, name: str, arguments: dict[str, Any], *, writable: bool) -> str:
        try:
            if name == "workspace_list_files":
                return self.list_files(str(arguments.get("directory", ".")))
            if name == "workspace_read_file":
                return self.read_file(str(arguments.get("path", "")))
            if name == "workspace_search_files":
                return self.search_files(
                    str(arguments.get("query", "")),
                    str(arguments.get("directory", ".")),
                )
            if name == "workspace_write_file":
                return self.write_file(
                    str(arguments.get("path", "")),
                    str(arguments.get("content", "")),
                    writable=writable,
                )
            return f"Tool error: unsupported tool name {name!r}."
        except WorkspaceError as exc:
            return f"Tool error: {exc}"
