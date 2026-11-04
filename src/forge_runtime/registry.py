"""Adapter that reads AgentForge catalogs and Markdown files.

No hosted API or AgentForge Python registry package is assumed.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Callable
import httpx
from forge_runtime.models import AgentDefinition, SkillDefinition


class RegistryError(RuntimeError):
    """The AgentForge source cannot be loaded or validated."""


class AgentForgeRegistry:
    def __init__(self, local_path: Path | None = None,
                 repository: str = "https://github.com/mhingan/agent-forge",
                 ref: str = "main", timeout: float = 20.0) -> None:
        self.local_path = local_path
        self.repository = repository.rstrip("/")
        self.ref = ref
        self.timeout = timeout
        self._agents: dict[str, AgentDefinition] = {}
        self._skills: dict[str, SkillDefinition] = {}

    def load(self) -> None:
        if self.local_path is not None:
            self._load_local()
        else:
            self._load_remote()

    def _read_local(self, relative: str) -> str:
        assert self.local_path is not None
        root = self.local_path.resolve()
        path = (root / relative).resolve()
        if root not in path.parents:
            raise RegistryError(f"Registry path escapes root: {relative}")
        return path.read_text(encoding="utf-8")

    def _load_local(self) -> None:
        try:
            assert self.local_path is not None
            self._consume(json.loads(self._read_local("catalog/agents.json")),
                          json.loads(self._read_local("catalog/skills.json")), self._read_local)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RegistryError(f"Could not load local AgentForge: {exc}") from exc

    def _load_remote(self) -> None:
        repo = self.repository.removeprefix("https://github.com/")
        base = f"https://raw.githubusercontent.com/{repo}/{self.ref}"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                agents = client.get(f"{base}/catalog/agents.json")
                skills = client.get(f"{base}/catalog/skills.json")
                agents.raise_for_status()
                skills.raise_for_status()
                cache: dict[str, str] = {}
                def read(path: str) -> str:
                    if path not in cache:
                        response = client.get(f"{base}/{path}")
                        response.raise_for_status()
                        cache[path] = response.text
                    return cache[path]
                self._consume(agents.json(), skills.json(), read)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RegistryError(f"Could not load AgentForge at {base}: {exc}") from exc

    def _consume(self, agents_doc: dict[str, Any], skills_doc: dict[str, Any],
                 read: Callable[[str], str]) -> None:
        self._agents.clear()
        self._skills.clear()
        agents = agents_doc.get("agents", [])
        skills = skills_doc.get("skills", [])
        if not isinstance(agents, list) or not isinstance(skills, list):
            raise RegistryError("Catalogs must contain agents and skills arrays.")
        for item in agents:
            name = str(item["name"])
            path = str(item.get("path") or f"agents/{name}.md")
            self._agents[name] = AgentDefinition(name=name,
                description=str(item.get("description", "")), path=path, content=read(path),
                recommended_skills=tuple(item.get("recommended_skills", [])),
                mode=str(item.get("mode", "subagent")))
        for item in skills:
            name = str(item["name"])
            path = str(item.get("path") or f"skills/{name}/SKILL.md")
            content = read(path)
            description = str(item.get("description", ""))
            if not description:
                match = re.search(r"(?m)^description:\\s*[\\\"']?(.+?)[\\\"']?\\s*$", content)
                description = match.group(1) if match else name
            self._skills[name] = SkillDefinition(name=name, description=description,
                                                   path=path, content=content)

    @property
    def agents(self) -> dict[str, AgentDefinition]:
        return dict(self._agents)

    @property
    def skills(self) -> dict[str, SkillDefinition]:
        return dict(self._skills)

    def get_agent(self, name: str) -> AgentDefinition:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise RegistryError(f"Unknown agent: {name}") from exc

    def get_skill(self, name: str) -> SkillDefinition:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise RegistryError(f"Unknown skill: {name}") from exc
