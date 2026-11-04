from pathlib import Path

import pytest

from forge_runtime.workspace import WorkspaceError, WorkspaceTools


def test_read_and_list_workspace_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    tools = WorkspaceTools(tmp_path)

    assert "src/" in tools.list_files()
    assert tools.read_file("src/app.py") == "print('hello')\n"


def test_search_workspace_files_returns_matching_lines(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def create_user():\n    return True\n", encoding="utf-8")
    tools = WorkspaceTools(tmp_path)

    result = tools.search_files("create_user")
    assert "app.py:1" in result
    assert "def create_user" in result


def test_read_write_agent_can_write_inside_workspace(tmp_path: Path) -> None:
    tools = WorkspaceTools(tmp_path)
    result = tools.execute_tool(
        "workspace_write_file",
        {"path": "src/new.py", "content": "VALUE = 42\n"},
        writable=True,
    )

    assert "Wrote src/new.py" in result
    assert (tmp_path / "src" / "new.py").read_text(encoding="utf-8") == "VALUE = 42\n"


def test_read_only_agent_cannot_write(tmp_path: Path) -> None:
    tools = WorkspaceTools(tmp_path)
    result = tools.execute_tool(
        "workspace_write_file",
        {"path": "src/new.py", "content": "VALUE = 42"},
        writable=False,
    )

    assert result.startswith("Tool error:")
    assert not (tmp_path / "src" / "new.py").exists()
    assert all(
        tool["name"] != "workspace_write_file"
        for tool in tools.tool_schemas(writable=False)
    )


@pytest.mark.parametrize("path", ["../outside.txt", "/tmp/outside.txt", "src/../../secret"])
def test_path_traversal_is_rejected(tmp_path: Path, path: str) -> None:
    tools = WorkspaceTools(tmp_path)
    with pytest.raises(WorkspaceError):
        tools.read_file(path)


def test_secret_environment_files_are_protected(tmp_path: Path) -> None:
    tools = WorkspaceTools(tmp_path)
    with pytest.raises(WorkspaceError, match="Secret environment"):
        tools.write_file(".env", "API_KEY=not-for-agents", writable=True)


def test_oversized_file_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "large.txt"
    target.write_text("x" * (WorkspaceTools.MAX_READ_BYTES + 1), encoding="utf-8")
    tools = WorkspaceTools(tmp_path)

    with pytest.raises(WorkspaceError, match="maximum supported read"):
        tools.read_file("large.txt")
