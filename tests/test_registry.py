from pathlib import Path

import pytest

from forge_runtime.registry import AgentForgeRegistry, RegistryError


def test_loads_published_agentforge_toolkit() -> None:
    registry = AgentForgeRegistry(source="installed")
    registry.load()

    assert registry.loaded_from is not None
    assert registry.loaded_from.startswith("agentforge-toolkit:")
    assert "architect" in registry.agents
    assert "backend-engineer" in registry.agents
    assert len(registry.skills) >= 18
    assert registry.rules
    assert registry.workflows
    assert registry.get_agent("architect").mode == "read-write"
    assert "architecture" in registry.get_agent("architect").recommended_skills


def test_local_registry_rejects_catalog_path_traversal(tmp_path: Path) -> None:
    registry = AgentForgeRegistry(local_path=tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("must not be read", encoding="utf-8")

    with pytest.raises(RegistryError, match="Unsafe path"):
        registry._safe_relative_path("../outside.md")


def test_explicit_installed_source_fails_clearly_when_package_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AgentForgeRegistry, "_installed_data_root", staticmethod(lambda: None))
    registry = AgentForgeRegistry(source="installed")

    with pytest.raises(RegistryError, match="agentforge-toolkit is not installed"):
        registry.load()
