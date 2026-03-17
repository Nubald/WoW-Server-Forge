"""Centralized logging service — writes to file and emits to EventBus."""
from __future__ import annotations

import logging
import threading
from collections import deque
from pathlib import Path
from datetime import datetime

from services.event_bus import get_bus


class LogService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def init(self, logs_dir: Path) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._lines: deque[str] = deque(maxlen=5000)
        self._bus = get_bus()

        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"forge_{datetime.now().strftime('%Y%m%d')}.log"

        self._logger = logging.getLogger("ServerForge")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            self._logger.addHandler(fh)

    def log(self, message: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self._lines.append(entry)
        getattr(self._logger, level, self._logger.info)(message)
        self._bus.emit("log.line", {"level": level, "message": entry})

    def info(self, msg: str)    -> None: self.log(msg, "info")
    def warning(self, msg: str) -> None: self.log(msg, "warning")
    def error(self, msg: str)   -> None: self.log(msg, "error")
    def debug(self, msg: str)   -> None: self.log(msg, "debug")

    def get_recent(self, n: int = 200) -> list[str]:
        return list(self._lines)[-n:]


def get_log() -> LogService:
    return LogService()
