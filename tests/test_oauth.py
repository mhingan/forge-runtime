import asyncio
from urllib.parse import urlsplit

import pytest

from forge_runtime.oauth import LoopbackOAuthFlow


@pytest.mark.asyncio
async def test_loopback_oauth_callback_returns_authorization_code_and_state():
    flow = LoopbackOAuthFlow(timeout_seconds=5)
    await flow.start()
    try:
        parsed = urlsplit(flow.redirect_uri or "")
        assert parsed.hostname == "127.0.0.1"
        assert parsed.path == "/oauth/callback"
        reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
        writer.write(
            b"GET /oauth/callback?code=authorization-code&state=expected-state HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\nConnection: close\r\n\r\n"
        )
        await writer.drain()
        code, state = await flow.callback_handler()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
        assert (code, state) == ("authorization-code", "expected-state")
        assert b"Authentication received" in response
    finally:
        await flow.close()


@pytest.mark.asyncio
async def test_loopback_oauth_callback_rejects_provider_denial():
    flow = LoopbackOAuthFlow(timeout_seconds=5)
    await flow.start()
    try:
        parsed = urlsplit(flow.redirect_uri or "")
        reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
        writer.write(
            b"GET /oauth/callback?error=access_denied&state=expected-state HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\nConnection: close\r\n\r\n"
        )
        await writer.drain()
        with pytest.raises(RuntimeError, match="rejected"):
            await flow.callback_handler()
        await reader.read()
        writer.close()
        await writer.wait_closed()
    finally:
        await flow.close()


def test_oauth_provider_matches_supported_mcp_sdk_contract():
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata
    from pydantic import AnyUrl

    class MemoryStorage:
        async def get_tokens(self):
            return None

        async def set_tokens(self, tokens):
            return None

        async def get_client_info(self):
            return None

        async def set_client_info(self, client_info):
            return None

    async def redirect_handler(_url):
        return None

    async def callback_handler():
        return "code", "state"

    provider = OAuthClientProvider(
        server_url="https://mcp.example.com",
        client_metadata=OAuthClientMetadata(
            client_name="Forge Runtime",
            redirect_uris=[AnyUrl("http://127.0.0.1:8765/oauth/callback")],
            token_endpoint_auth_method="none",
        ),
        storage=MemoryStorage(),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
        timeout=5.0,
    )
    assert isinstance(provider, object)
