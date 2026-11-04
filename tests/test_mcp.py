from forge_runtime.mcp import MCPManager, _tool_name


def test_mcp_tool_names_are_namespaced_and_safe():
    assert _tool_name("figma", "get-file") == "forge_figma_get_file"
    assert _tool_name("My Server", "read file") == "forge_my_server_read_file"


def test_mcp_tool_output_redacts_connection_secrets():
    manager = MCPManager()
    manager._secrets_by_server = {"figma": ["figma-secret", "short"]}
    result = manager._redact("figma", "token=figma-secret and short token")
    assert result == "token=[REDACTED] and [REDACTED] token"
    assert "figma-secret" not in result
