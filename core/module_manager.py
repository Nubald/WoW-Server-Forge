"""Module manager — enable/disable mods like Eluna, NPC Bots, etc."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Generator

from models.module_definition import ModuleDefinition
from app.constants import MODULES_DIR
from core.source_manager import SourceManager
from services.event_bus import get_bus
from services.log_service import get_log


class ModuleManager:
    """Loads module definitions and handles enabling/disabling them in a repo."""

    def __init__(self):
        self._bus = get_bus()
        self._log = get_log()
        self._source = SourceManager()
        self._definitions: dict[str, ModuleDefinition] = {}
        self._load_definitions()

    def _load_definitions(self) -> None:
        if not MODULES_DIR.exists():
            return
        for json_file in MODULES_DIR.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                mod = ModuleDefinition.from_dict(data)
                self._definitions[mod.id] = mod
            except Exception as e:
                self._log.warning(f"Failed to load module {json_file.name}: {e}")

    def get_all(self) -> dict[str, ModuleDefinition]:
        return self._definitions

    def get_compatible(self, server_id: str) -> list[ModuleDefinition]:
        return [m for m in self._definitions.values()
                if not m.compatible_servers or server_id in m.compatible_servers]

    def validate(self, enabled: set[str]) -> list[str]:
        """Return list of conflict error messages."""
        errors = []
        for mid in enabled:
            mod = self._definitions.get(mid)
            if not mod:
                continue
            for incompatible in mod.incompatible_with:
                if incompatible in enabled:
                    errors.append(
                        f"'{mod.display_name}' is incompatible with '{incompatible}'"
                    )
        return errors

    def get_cmake_options(self, enabled: set[str]) -> dict[str, str]:
        """Collect CMake options contributed by all enabled modules."""
        options = {}
        for mid in enabled:
            mod = self._definitions.get(mid)
            if mod:
                options.update(mod.cmake_options)
        return options

    def enable_module(self, module_id: str, repo_path: Path,
                      branch: str = "master") -> Generator[str, None, None]:
        mod = self._definitions.get(module_id)
        if not mod:
            yield f"[ERROR] Module not found: {module_id}"
            return

        yield f"[MODULE] Enabling {mod.display_name}..."

        if mod.repo.integration_type == "submodule":
            # Guard: the repo must exist and be a git repository
            if not repo_path.exists():
                yield (f"[ERROR] Source directory not found: {repo_path}")
                yield  "[INFO]  Clone the server source first (Source tab)."
                return
            if not (repo_path / ".git").exists():
                yield (f"[ERROR] {repo_path} is not a git repository.")
                yield  "[INFO]  Clone the server source first (Source tab)."
                return

            target = repo_path / mod.repo.target_path
            if target.exists() and (target / ".git").exists():
                yield f"[OK] {mod.display_name} already present at {target}, updating..."
                yield from self._source.update(target)
            else:
                yield from self._source.add_submodule(
                    repo_path, mod.repo.url,
                    mod.repo.target_path, mod.repo.branch or branch
                )
        elif mod.repo.integration_type == "cmake_option":
            yield f"[MODULE] {mod.display_name} enabled via CMake options (no file changes needed)"

        yield f"[OK] {mod.display_name} enabled"

    def disable_module(self, module_id: str, repo_path: Path) -> Generator[str, None, None]:
        mod = self._definitions.get(module_id)
        if not mod:
            yield f"[ERROR] Module not found: {module_id}"
            return
        yield f"[MODULE] Disabling {mod.display_name} (manual cleanup may be needed)..."
        yield f"[INFO]  Target path: {repo_path / mod.repo.target_path}"
