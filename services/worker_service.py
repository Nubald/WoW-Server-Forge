"""Background task worker service using ThreadPoolExecutor."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Optional


class WorkerService:
    """Manages background tasks with named slots and cancellation support."""

    _instance: Optional["WorkerService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "WorkerService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="forge")
                cls._instance._futures: dict[str, Future] = {}
        return cls._instance

    def submit(self, name: str, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """Submit a background task. If a task with the same name is running, cancel it first."""
        existing = self._futures.get(name)
        if existing and not existing.done():
            existing.cancel()

        future = self._executor.submit(fn, *args, **kwargs)
        self._futures[name] = future
        return future

    def is_running(self, name: str) -> bool:
        f = self._futures.get(name)
        return f is not None and not f.done()

    def cancel(self, name: str) -> bool:
        f = self._futures.get(name)
        if f:
            return f.cancel()
        return False

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def get_workers() -> WorkerService:
    return WorkerService()
