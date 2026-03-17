"""Thread-safe publish/subscribe event bus.

All background threads emit events here. The bus routes them to the main
thread via root.after(0, ...) so UI widgets are always updated safely.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable, Optional


class EventBus:
    """Singleton event bus with thread-safe dispatch."""

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._handlers: dict[str, list[Callable]] = defaultdict(list)
                cls._instance._root = None
        return cls._instance

    def set_root(self, root: Any) -> None:
        """Bind the tkinter root so we can use root.after for thread safety."""
        self._root = root

    def subscribe(self, event: str, handler: Callable) -> None:
        if handler not in self._handlers[event]:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            pass

    def emit(self, event: str, payload: Any = None) -> None:
        """Emit an event. Safe to call from any thread."""
        handlers = list(self._handlers.get(event, []))
        if not handlers:
            return
        if self._root is not None:
            self._root.after(0, self._dispatch, event, payload, handlers)
        else:
            self._dispatch(event, payload, handlers)

    def _dispatch(self, event: str, payload: Any, handlers: list[Callable]) -> None:
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                print(f"[EventBus] Error in handler for '{event}': {exc}")


# Convenience singleton accessor
_bus = EventBus()


def get_bus() -> EventBus:
    return _bus
