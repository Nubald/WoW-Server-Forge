"""Abstract base class for all views."""
from __future__ import annotations

import customtkinter as ctk
from app.constants import COLOR_BG_DARK


class BaseView(ctk.CTkFrame):
    """All page views inherit from this."""

    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_DARK, corner_radius=0, **kwargs)
        self.app = app
        self.state = app.state
        self.bus = app.bus
        self._ui_built = False

    def on_enter(self) -> None:
        """Called when this view becomes active."""
        if not self._ui_built:
            self.build_ui()
            self._ui_built = True
        self._subscribe_events()
        self.refresh()

    def on_exit(self) -> None:
        """Called when navigating away."""
        self._unsubscribe_events()

    def build_ui(self) -> None:
        """Build widgets. Called once on first show."""

    def refresh(self) -> None:
        """Refresh displayed data from app state. Called on every enter."""

    def _subscribe_events(self) -> None:
        """Subscribe to EventBus events."""

    def _unsubscribe_events(self) -> None:
        """Unsubscribe from EventBus events."""

    def _header(self, parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
        """Render a standard page header."""
        from app.constants import COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY
        frame = ctk.CTkFrame(parent, fg_color="transparent", height=64)
        frame.pack(fill="x", padx=24, pady=(20, 0))
        frame.pack_propagate(False)

        ctk.CTkLabel(
            frame, text=title,
            font=ctk.CTkFont("Segoe UI", 20, "bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(anchor="w")

        if subtitle:
            ctk.CTkLabel(
                frame, text=subtitle,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w"
            ).pack(anchor="w")
        return frame
