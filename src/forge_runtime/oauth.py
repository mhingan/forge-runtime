"""OAuth 2.1 authorization-code/PKCE support for remote MCP servers."""

from __future__ import annotations

import asyncio
import sys
import webbrowser
from contextlib import asynccontextmanager, suppress
from urllib.parse import parse_qs, urlsplit

import httpx2
from forge_mcp.config import MCPConnection
from pydantic import AnyUrl
from forge_runtime.credentials import CredentialVault

OAUTH_TIMEOUT_SECONDS = 300


class KeyringOAuthStorage:
    """Persist OAuth access/refresh tokens and registered client metadata in the OS vault."""

    def __init__(self, vault: CredentialVault, connection_name: str) -> None:
        self.vault = vault
        self.tokens_ref = f"mcp/{connection_name}/oauth/tokens"
        self.client_ref = f"mcp/{connection_name}/oauth/client"

    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken

        try:
            value = self.vault.get(self.tokens_ref)
        except KeyError:
            return None
        return OAuthToken.model_validate_json(value)

    async def set_tokens(self, tokens) -> None:
        self.vault.set(self.tokens_ref, tokens.model_dump_json())

    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull

        try:
            value = self.vault.get(self.client_ref)
        except KeyError:
            return None
        return OAuthClientInformationFull.model_validate_json(value)

    async def set_client_info(self, client_info) -> None:
        self.vault.set(self.client_ref, client_info.model_dump_json())


class LoopbackOAuthFlow:
    """One-time, random-port loopback receiver for OAuth authorization callbacks.

    Only listens on 127.0.0.1. Authorization state and PKCE validation are performed
    by the official MCP SDK before tokens are accepted.
    """

    def __init__(self, timeout_seconds: int = OAUTH_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds
        self._server: asyncio.AbstractServer | None = None
        self._result: asyncio.Future[AuthorizationCodeResult] | None = None
        self.redirect_uri: str | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._result = loop.create_future()
        self._server = await asyncio.start_server(
            self._handle_client, host="127.0.0.1", port=0, limit=16 * 1024
        )
        sockets = self._server.sockets or []
        if not sockets:
            raise RuntimeError("Could not create a local OAuth callback listener.")
        port = int(sockets[0].getsockname()[1])
        self.redirect_uri = f"http://127.0.0.1:{port}/oauth/callback"

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._result is not None and not self._result.done():
            self._result.cancel()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        status = "400 Bad Request"
        body = "Invalid OAuth callback. Return to the Forge terminal."
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = line.decode("ascii", errors="strict").strip().split(" ")
            if len(parts) != 3 or parts[0] != "GET":
                raise ValueError("Invalid callback request.")
            target = urlsplit(parts[1])
            if target.path != "/oauth/callback":
                raise ValueError("Invalid callback path.")
            params = parse_qs(target.query, strict_parsing=False)
            if params.get("error"):
                raise RuntimeError("The identity provider denied OAuth authorization.")
            code = (params.get("code") or [""])[0]
            state = (params.get("state") or [None])[0]
            issuer = (params.get("iss") or [None])[0]
            if not code or not state:
                raise ValueError("OAuth callback is missing its code or state.")
            future = self._result
            if future is None or future.done():
                raise ValueError("No OAuth authorization request is awaiting a callback.")
            future.set_result(AuthorizationCodeResult(code=code, state=state, iss=issuer))
            status = "200 OK"
            body = "Authentication received. You can close this browser tab and return to Forge."
        except Exception:
            future = self._result
            if future is not None and not future.done():
                future.set_exception(RuntimeError("OAuth callback was invalid or rejected."))
        try:
            payload = body.encode("utf-8")
            writer.write(
                (
                    f"HTTP/1.1 {status}\r\n"
                    "Content-Type: text/plain; charset=utf-8\r\n"
                    "Cache-Control: no-store\r\n"
                    "X-Content-Type-Options: nosniff\r\n"
                    f"Content-Length: {len(payload)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
                + payload
            )
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()

    async def redirect_handler(self, authorization_url: str) -> None:
        if self._result is None or self._result.done():
            self._result = asyncio.get_running_loop().create_future()
        opened = False
        try:
            opened = webbrowser.open(authorization_url, new=1, autoraise=True)
        except Exception:
            opened = False
        if not opened:
            sys.stderr.write(
                "\nForge needs you to authorize this MCP server in your browser:\n"
                f"{authorization_url}\n\n"
            )
            sys.stderr.flush()

    async def callback_handler(self) -> AuthorizationCodeResult:
        if self._result is None:
            raise RuntimeError("OAuth callback listener has not been started.")
        return await asyncio.wait_for(self._result, timeout=self.timeout_seconds)


@asynccontextmanager
async def oauth_http_client(
    connection: MCPConnection,
    vault: CredentialVault,
):
    """Yield an authenticated HTTPX client for one remote MCP connection."""
    if connection.transport != "http" or not connection.url:
        raise ValueError("OAuth is available only for remote HTTP MCP connections.")
    if connection.auth_mode != "oauth":
        raise ValueError("This MCP connection is not configured for OAuth.")

    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata

    flow = LoopbackOAuthFlow()
    await flow.start()
    try:
        metadata = OAuthClientMetadata(
            client_name="Forge Runtime",
            redirect_uris=[AnyUrl(flow.redirect_uri)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
            scope=connection.oauth_scope,
        )
        provider = OAuthClientProvider(
            server_url=connection.url,
            client_metadata=metadata,
            storage=KeyringOAuthStorage(vault, connection.name),
            redirect_handler=flow.redirect_handler,
            callback_handler=flow.callback_handler,
        )
        async with httpx2.AsyncClient(auth=provider, timeout=30.0) as client:
            yield client
    finally:
        await flow.close()
