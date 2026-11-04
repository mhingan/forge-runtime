"""Managed MCP client connections for Forge Runtime.

Only explicitly enabled connections are started. Registry data and MCP tool
descriptions are untrusted input. Credentials are resolved from the OS keyring
and passed only to the specific MCP subprocess or HTTPS connection.
"""
from __future__ import annotations

import json
import os
import re
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from forge_mcp.config import ConnectionStore
from forge_runtime.credentials import CredentialVault

SAFE_NAME = re.compile(r"[^a-zA-Z0-9_]")


def _tool_name(server: str, tool: str) -> str:
    value = SAFE_NAME.sub("_", f"forge_{server}_{tool}").strip("_").lower()
    return value[:64]


def _minimal_child_environment() -> dict[str, str]:
    allowed = {"PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
               "SYSTEMROOT", "WINDIR", "APPDATA", "USERPROFILE"}
    return {key: value for key, value in os.environ.items() if key in allowed}


class MCPManager:
    """Maintains enabled MCP sessions and dispatches namespaced tool calls."""

    def __init__(
        self,
        store: ConnectionStore | None = None,
        vault: CredentialVault | None = None,
        max_tools: int = 128,
        result_chars: int = 16000,
    ) -> None:
        self.store = store or ConnectionStore(
            Path(os.getenv("FORGE_MCP_CONFIG", Path.home() / ".forge" / "mcp.json"))
        )
        self.vault = vault or CredentialVault()
        self.max_tools = max_tools
        self.result_chars = result_chars
        self._stack: AsyncExitStack | None = None
        self._sessions: dict[str, Any] = {}
        self._tools: dict[str, dict[str, Any]] = {}
        self._secrets_by_server: dict[str, list[str]] = {}
        self.startup_errors: list[str] = []

    async def start(self) -> "MCPManager":
        if self._stack is not None:
            return self
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError('MCP support is missing. Install with: pip install "forge-agent-runtime"') from exc

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        try:
            connections = self.store.load()
        except Exception:
            await self.close()
            raise

        for name, connection in connections.items():
            if not connection.enabled:
                continue
            if len(self._tools) >= self.max_tools:
                self.startup_errors.append(f"{name}: skipped (tool limit reached)")
                continue
            try:
                if connection.transport == "stdio":
                    env = _minimal_child_environment()
                    process_home = Path.home() / ".forge" / "mcp-homes" / name
                    if process_home.is_symlink():
                        raise ValueError("Refusing to use a symlinked MCP process home.")
                    process_home.mkdir(parents=True, exist_ok=True, mode=0o700)
                    os.chmod(process_home, 0o700)
                    env["HOME"] = str(process_home)
                    if os.name == "nt":
                        env["USERPROFILE"] = str(process_home)
                    for variable, reference in (connection.env_refs or {}).items():
                        secret = self.vault.get(reference)
                        env[variable] = secret
                        self._secrets_by_server.setdefault(name, []).append(secret)
                    params = StdioServerParameters(
                        command=connection.command or "",
                        args=list(connection.args),
                        env=env,
                        cwd=connection.cwd,
                    )
                    read_stream, write_stream = await self._stack.enter_async_context(
                        stdio_client(params)
                    )
                else:
                    headers = {}
                    for key, reference in (connection.header_refs or {}).items():
                        secret = self.vault.get(reference)
                        headers[key] = secret
                        self._secrets_by_server.setdefault(name, []).append(secret)
                    read_stream, write_stream, _ = await self._stack.enter_async_context(
                        streamablehttp_client(connection.url or "", headers=headers)
                    )

                session = await self._stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                result = await session.list_tools()
                self._sessions[name] = session
                for item in result.tools:
                    original_name = str(item.name)
                    if connection.allowed_tools and original_name not in connection.allowed_tools:
                        continue
                    exposed_name = _tool_name(name, original_name)
                    if exposed_name in self._tools:
                        self.startup_errors.append(
                            f"{name}.{original_name}: skipped (tool-name collision)"
                        )
                        continue
                    schema = getattr(item, "inputSchema", None) or {
                        "type": "object", "properties": {}
                    }
                    if not isinstance(schema, dict):
                        schema = {"type": "object", "properties": {}}
                    self._tools[exposed_name] = {
                        "server": name,
                        "original_name": original_name,
                        "description": str(getattr(item, "description", "") or "")[:2000],
                        "parameters": schema,
                    }
                    if len(self._tools) >= self.max_tools:
                        break
            except KeyError as exc:
                self.startup_errors.append(f"{name}: missing credential {str(exc).strip(chr(39))}")
            except Exception as exc:
                self.startup_errors.append(
                    f"{name}: connection failed ({type(exc).__name__}); review server setup and credentials"
                )
        return self

    async def close(self) -> None:
        if self._stack is not None:
            stack, self._stack = self._stack, None
            await stack.aclose()
        self._sessions.clear()
        self._tools.clear()
        self._secrets_by_server.clear()

    async def __aenter__(self) -> "MCPManager":
        return await self.start()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {"name": exposed, "description": f"MCP server {meta['server']}: {meta['description']}",
             "parameters": meta["parameters"]}
            for exposed, meta in self._tools.items()
        ]

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": exposed, "server": meta["server"],
             "original_name": meta["original_name"],
             "description": meta["description"], "input_schema": meta["parameters"]}
            for exposed, meta in self._tools.items()
        ]

    def _redact(self, server: str, value: str) -> str:
        for secret in sorted(self._secrets_by_server.get(server, []), key=len, reverse=True):
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        meta = self._tools.get(name)
        if meta is None:
            return f"MCP tool error: unknown or unavailable tool {name!r}."
        session = self._sessions.get(meta["server"])
        if session is None:
            return f"MCP tool error: server {meta['server']!r} is not connected."
        try:
            result = await session.call_tool(meta["original_name"], arguments)
            pieces: list[str] = []
            for item in getattr(result, "content", []) or []:
                text = getattr(item, "text", None)
                if text is not None:
                    pieces.append(str(text))
                elif hasattr(item, "model_dump"):
                    pieces.append(json.dumps(item.model_dump(), ensure_ascii=False, default=str))
                else:
                    pieces.append(str(item))
            output = "\n".join(pieces) or json.dumps(
                getattr(result, "structuredContent", None), ensure_ascii=False, default=str
            )
            if getattr(result, "isError", False):
                output = "MCP server reported an error: " + output
            output = self._redact(meta["server"], output)
            return output[: self.result_chars]
        except Exception as exc:
            detail = self._redact(meta["server"], str(exc))
            return f"MCP tool error ({type(exc).__name__}): {detail[:1000]}"

    def status(self) -> dict[str, Any]:
        return {
            "connected_servers": sorted(self._sessions),
            "tool_count": len(self._tools),
            "startup_errors": list(self.startup_errors),
        }
