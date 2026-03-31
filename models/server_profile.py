"""ServerProfile dataclass — the single source of truth for a user's server config."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class DbConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "trinity"
    password: str = "trinity"
    auth_db: str = "auth"
    characters_db: str = "characters"
    world_db: str = "world"
    hotfixes_db: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "DbConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class NetworkConfig:
    realm_name: str = "My WoW Server"
    bind_ip: str = "0.0.0.0"
    auth_port: int = 3724
    world_port: int = 8085
    soap_enabled: bool = False
    soap_port: int = 7878
    ra_enabled: bool = False
    ra_port: int = 3443
    external_ip: str = "127.0.0.1"

    @classmethod
    def from_dict(cls, d: dict) -> "NetworkConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ServerProfile:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "My Server"
    server_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    workspace_dir: str = ""
    source_dir: str = ""
    build_dir: str = ""
    install_dir: str = ""
    enabled_modules: list[str] = field(default_factory=list)
    db_config: DbConfig = field(default_factory=DbConfig)
    network_config: NetworkConfig = field(default_factory=NetworkConfig)
    cmake_extra_options: dict[str, str] = field(default_factory=dict)
    last_build_commit: str = ""
    build_type: str = "RelWithDebInfo"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ServerProfile":
        db = DbConfig.from_dict(d.pop("db_config", {}))
        net = NetworkConfig.from_dict(d.pop("network_config", {}))
        fields = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(db_config=db, network_config=net, **fields)

    def save(self, profiles_dir: Path) -> Path:
        profiles_dir.mkdir(parents=True, exist_ok=True)
        path = profiles_dir / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "ServerProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def load_all(cls, profiles_dir: Path) -> list["ServerProfile"]:
        profiles = []
        if profiles_dir.exists():
            for p in sorted(profiles_dir.glob("*.json")):
                try:
                    profiles.append(cls.load(p))
                except Exception:
                    pass
        return profiles
