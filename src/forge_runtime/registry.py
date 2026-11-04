"""AgentForge registry adapter.

The published agentforge-toolkit distribution exposes agentforge.core.data_root.
Forge Runtime reads the packaged catalog by default, with local and GitHub fallbacks.
Registry files are untrusted prompt content and are never executed.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import httpx

from forge_runtime.models import AgentDefinition, SkillDefinition

RegistrySource = Literal["auto", "installed", "local", "github"]


class RegistryError(RuntimeError):
    """The AgentForge registry source is unavailable or invalid."""


class AgentForgeRegistry:
    def __init__(
        self,
        local_path: Path | None = None,
        repository: str = "https://github.com/mhingan/agent-forge",
        ref: str = "main",
        timeout: float = 20.0,
        source: RegistrySource = "auto",
    ) -> None:
        self.local_path = local_path
        self.repository = repository.rstrip("/").removesuffix(".git")
        self.ref = ref
        self.timeout = timeout
        self.source = "local" if local_path is not None else source
        self.loaded_from: str | None = None
        self._agents: dict[str, AgentDefinition] = {}
        self._skills: dict[str, SkillDefinition] = {}
        self._rules: dict[str, str] = {}
        self._workflows: dict[str, str] = {}

    @staticmethod
    def _safe_relative_path(value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
            raise RegistryError(f"Unsafe path in AgentForge catalog: {value!r}")
        return path.as_posix()

    def load(self) -> None:
        """Load selected source and refresh all indexes."""
        if self.local_path is not None or self.source == "local":
            if self.local_path is None:
                raise RegistryError("source='local' requires local_path.")
            self._load_directory(self.local_path)
            self.loaded_from = str(self.local_path.resolve())
            return

        if self.source in {"auto", "installed"}:
            root = self._installed_data_root()
            if root is not None:
                self._load_directory(root)
                self.loaded_from = f"agentforge-toolkit:{root}"
                return
            if self.source == "installed":
                raise RegistryError(
                    "agentforge-toolkit is not installed. Install forge-runtime dependencies "
                    "or select source='github'."
                )

        if self.source in {"auto", "github"}:
            self._load_remote()
            self.loaded_from = f"{self.repository}@{self.ref}"
            return
        raise RegistryError(f"Unsupported registry source: {self.source}")

    @staticmethod
    def _installed_data_root() -> Path | None:
        try:
            from agentforge.core import data_root
        except ImportError:
            return None
        try:
            root = Path(data_root()).resolve()
        except (OSError, RuntimeError, FileNotFoundError) as exc:
            raise RegistryError(f"agentforge-toolkit could not resolve its data directory: {exc}") from exc
        if not root.is_dir():
            raise RegistryError(f"AgentForge data directory does not exist: {root}")
        return root

    @staticmethod
    def _read_from_root(root: Path, relative: str) -> str:
        safe = AgentForgeRegistry._safe_relative_path(relative)
        resolved_root = root.resolve()
        path = (resolved_root / safe).resolve()
        if resolved_root not in path.parents or not path.is_file():
            raise RegistryError(f"AgentForge file is missing or escapes its root: {relative}")
        return path.read_text(encoding="utf-8")

    def _load_directory(self, root: Path) -> None:
        root = root.resolve()
        try:
            agents_doc = json.loads(self._read_from_root(root, "catalog/agents.json"))
            skills_doc = json.loads(self._read_from_root(root, "catalog/skills.json"))
            def read(relative: str) -> str:
                return self._read_from_root(root, relative)
            self._consume(agents_doc, skills_doc, read)
            self._rules = self._read_markdown_directory(root, "rules")
            self._workflows = self._read_markdown_directory(root, "workflows")
        except RegistryError:
            raise
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise RegistryError(f"Could not load AgentForge files from {root}: {exc}") from exc

    @staticmethod
    def _read_markdown_directory(root: Path, relative: str) -> dict[str, str]:
        directory = root / relative
        if not directory.is_dir():
            return {}
        docs: dict[str, str] = {}
        for path in sorted(directory.rglob("*.md")):
            resolved = path.resolve()
            if root not in resolved.parents:
                raise RegistryError(f"Markdown resource escapes AgentForge root: {path}")
            docs[path.relative_to(directory).as_posix()] = path.read_text(encoding="utf-8")
        return docs

    def _load_remote(self) -> None:
        repo = self.repository.removeprefix("https://github.com/")
        if "/" not in repo or repo.startswith("/") or "://" in repo:
            raise RegistryError(f"Invalid GitHub repository URL: {self.repository}")
        base = f"https://raw.githubusercontent.com/{repo}/{self.ref}"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                agent_response = client.get(f"{base}/catalog/agents.json")
                skill_response = client.get(f"{base}/catalog/skills.json")
                agent_response.raise_for_status()
                skill_response.raise_for_status()
                cache: dict[str, str] = {}
                def read(relative: str) -> str:
                    safe = self._safe_relative_path(relative)
                    if safe not in cache:
                        response = client.get(f"{base}/{safe}")
                        response.raise_for_status()
                        cache[safe] = response.text
                    return cache[safe]
                self._consume(agent_response.json(), skill_response.json(), read)
                self._rules = {}
                self._workflows = {}
        except RegistryError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RegistryError(f"Could not load AgentForge from {base}: {exc}") from exc

    def _consume(
        self,
        agents_doc: dict[str, Any],
        skills_doc: dict[str, Any],
        read: Callable[[str], str],
    ) -> None:
        agents = agents_doc.get("agents")
        skills = skills_doc.get("skills")
        if not isinstance(agents, list) or not isinstance(skills, list):
            raise RegistryError("AgentForge catalogs must contain agents and skills arrays.")
        loaded_agents: dict[str, AgentDefinition] = {}
        loaded_skills: dict[str, SkillDefinition] = {}
        for item in agents:
            if not isinstance(item, dict) or not item.get("name"):
                raise RegistryError("AgentForge agent catalog contains an invalid entry.")
            name = str(item["name"])
            if name in loaded_agents:
                raise RegistryError(f"Duplicate AgentForge agent name: {name}")
            path = self._safe_relative_path(str(item.get("path") or f"agents/{name}.md"))
            loaded_agents[name] = AgentDefinition(
                name=name,
                description=str(item.get("description", "")),
                path=path,
                content=read(path),
                recommended_skills=tuple(item.get("recommended_skills", [])),
                mode=str(item.get("default_mode") or item.get("mode") or "subagent"),
            )
        for item in skills:
            if not isinstance(item, dict) or not item.get("name"):
                raise RegistryError("AgentForge skill catalog contains an invalid entry.")
            name = str(item["name"])
            if name in loaded_skills:
                raise RegistryError(f"Duplicate AgentForge skill name: {name}")
            path = self._safe_relative_path(str(item.get("path") or f"skills/{name}/SKILL.md"))
            body = read(path)
            description = str(item.get("description") or name)
            skill_root = PurePosixPath(path).parent
            references: dict[str, str] = {}
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
                target = target.split("#", 1)[0].split("?", 1)[0].strip()
                if not target or "://" in target or target.startswith(("mailto:", "/")):
                    continue
                try:
                    reference_path = self._safe_relative_path(
                        (skill_root / target).as_posix()
                    )
                    if PurePosixPath(reference_path).parts[:len(skill_root.parts)] != skill_root.parts:
                        continue
                    references[target] = read(reference_path)
                except RegistryError:
                    continue
            loaded_skills[name] = SkillDefinition(
                name=name,
                description=description,
                path=path,
                content=body,
                references=references,
            )
        self._agents = loaded_agents
        self._skills = loaded_skills

    @property
    def agents(self) -> dict[str, AgentDefinition]:
        return dict(self._agents)

    @property
    def skills(self) -> dict[str, SkillDefinition]:
        return dict(self._skills)

    @property
    def rules(self) -> dict[str, str]:
        return dict(self._rules)

    @property
    def workflows(self) -> dict[str, str]:
        return dict(self._workflows)

    def get_agent(self, name: str) -> AgentDefinition:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise RegistryError(f"Unknown agent role: {name}") from exc

    def get_skill(self, name: str) -> SkillDefinition:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise RegistryError(f"Unknown skill: {name}") from exc
