"""Module definition dataclass."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ModuleRepo:
    url: str = ""
    branch: str = "master"
    integration_type: str = "submodule"  # "submodule" | "cmake_option" | "source_patch"
    target_path: str = ""


@dataclass
class ModuleDefinition:
    id: str = ""
    display_name: str = ""
    description: str = ""
    author: str = ""
    repo: ModuleRepo = field(default_factory=ModuleRepo)
    cmake_options: dict[str, str] = field(default_factory=dict)
    compatible_servers: list[str] = field(default_factory=list)
    incompatible_with: list[str] = field(default_factory=list)
    requires_db_patch: bool = False
    db_patch_dir: str = ""
    warning: str | None = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ModuleDefinition":
        repo_data = d.pop("repo", {})
        repo = ModuleRepo(**{k: v for k, v in repo_data.items() if k in ModuleRepo.__dataclass_fields__})
        fields = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(repo=repo, **fields)
