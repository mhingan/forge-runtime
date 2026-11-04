from pathlib import Path

import pytest

from forge_runtime.sandbox import DockerSandboxExecutor, SandboxError


class FakeSandboxExecutor(DockerSandboxExecutor):
    mode = "write"

    async def _run_container(self, snapshot, argv, timeout_seconds):
        if self.mode == "write":
            (snapshot / "app.py").write_text("print('updated')\n", encoding="utf-8")
            (snapshot / "new.py").write_text("VALUE = 42\n", encoding="utf-8")
            (snapshot / ".env").write_text("API_KEY=do-not-copy\n", encoding="utf-8")
            (snapshot / ".git").mkdir(exist_ok=True)
            (snapshot / ".git" / "config").write_text("credential=secret", encoding="utf-8")
            return 0, "tests passed\n", "", False, False
        if self.mode == "delete":
            (snapshot / "remove-me.txt").unlink()
            return 0, "", "", False, False
        return 1, "", "test failure\n", False, False


def make_workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('original')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("API_KEY=replace-me\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("private config", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "remove-me.txt").write_text("keep this file", encoding="utf-8")
    return tmp_path


def test_snapshot_excludes_secrets_git_and_dependency_directories(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    executor = DockerSandboxExecutor(root)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    manifest = executor._copy_workspace(snapshot)

    assert "src/app.py" in manifest
    assert ".env.example" in manifest
    assert ".env" not in manifest
    assert ".git/config" not in manifest
    assert "node_modules/package.json" not in manifest
    assert not (snapshot / ".env").exists()
    assert not (snapshot / ".git").exists()
    assert not (snapshot / "node_modules").exists()


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["docker", "ps"],
        ["curl", "https://example.com"],
        ["/bin/bash", "-lc", "id"],
        ["python", ""],
        ["python", "x" * 16_001],
    ],
)
def test_command_validation_rejects_unsafe_or_invalid_argv(argv) -> None:
    with pytest.raises(SandboxError):
        DockerSandboxExecutor.validate_argv(argv)


@pytest.mark.parametrize(
    "argv",
    [
        ["python", "-m", "pytest"],
        ["pytest", "-q"],
        ["ruff", "check", "."],
        ["npm", "test"],
        ["bash", "-lc", "python -m pytest"],
    ],
)
def test_command_validation_accepts_developer_commands(argv) -> None:
    assert DockerSandboxExecutor.validate_argv(argv) == argv


@pytest.mark.asyncio
async def test_read_write_agent_applies_only_safe_sandbox_changes(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    executor = FakeSandboxExecutor(root)

    result = await executor.run(["python", "-m", "pytest"], writable=True)

    assert result.exit_code == 0
    assert result.stdout == "tests passed\n"
    assert result.applied_files == ["new.py", "src/app.py"]
    assert (root / "src" / "app.py").read_text(encoding="utf-8") == "print('updated')\n"
    assert (root / "new.py").read_text(encoding="utf-8") == "VALUE = 42\n"
    assert (root / ".env").read_text(encoding="utf-8") == "API_KEY=secret\n"
    assert not (root / ".git" / "config").read_text(encoding="utf-8") == "credential=secret"


@pytest.mark.asyncio
async def test_read_only_agent_discards_all_sandbox_changes(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    executor = FakeSandboxExecutor(root)

    result = await executor.run(["pytest", "-q"], writable=False)

    assert result.exit_code == 0
    assert result.changes_discarded is True
    assert result.changed_files == ["new.py", "src/app.py"]
    assert result.applied_files == []
    assert (root / "src" / "app.py").read_text(encoding="utf-8") == "print('original')\n"
    assert not (root / "new.py").exists()


@pytest.mark.asyncio
async def test_sandbox_deletions_are_not_copied_back(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    executor = FakeSandboxExecutor(root)
    executor.mode = "delete"

    result = await executor.run(["python", "-m", "pytest"], writable=True)

    assert result.exit_code == 0
    assert (root / "remove-me.txt").exists()
    assert "deletions are not copied back" in result.stderr


@pytest.mark.asyncio
async def test_sandbox_output_cannot_write_through_workspace_symlink(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are not supported on this platform")

    class LinkWritingExecutor(FakeSandboxExecutor):
        async def _run_container(self, snapshot, argv, timeout_seconds):
            target = snapshot / "linked"
            target.mkdir(exist_ok=True)
            (target / "escape.txt").write_text("no", encoding="utf-8")
            return 0, "", "", False, False

    executor = LinkWritingExecutor(root)
    with pytest.raises(SandboxError, match="symlink"):
        await executor.run(["python", "-m", "pytest"], writable=True)
    assert not (outside / "escape.txt").exists()


def test_sandbox_tool_schema_requires_argv_and_caps_timeout(tmp_path: Path) -> None:
    executor = DockerSandboxExecutor(tmp_path)
    schema = executor.tool_schemas()[0]

    assert schema["name"] == "workspace_run_command"
    assert schema["parameters"]["required"] == ["argv"]
    assert schema["parameters"]["properties"]["timeout_seconds"]["maximum"] == 600
