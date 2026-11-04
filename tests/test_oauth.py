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
