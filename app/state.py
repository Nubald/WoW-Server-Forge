"""Global application state singleton."""
from __future__ import annotations

from collections import deque
from typing import Optional

from models.server_profile import ServerProfile


class AppState:
    """Single source of truth for mutable runtime state."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.active_profile: Optional[ServerProfile] = None
        self.server_status: dict[str, str] = {"auth": "stopped", "world": "stopped"}
        self.build_status: str = "IDLE"   # IDLE / BUILDING / SUCCESS / FAILED
        self.prereq_status: dict[str, bool] = {}
        self.log_lines: deque[str] = deque(maxlen=5000)
        self.server_defs: dict[str, dict] = {}   # loaded JSON definitions


def get_state() -> AppState:
    return AppState()
