"""Scrollable log console widget with color-coded levels."""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
from app.constants import (
    COLOR_BG_CARD, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_INFO, COLOR_ACCENT
)

LEVEL_COLORS = {
    "info":    COLOR_TEXT_PRIMARY,
    "warning": COLOR_WARNING,
    "error":   COLOR_ERROR,
    "success": COLOR_SUCCESS,
    "cmake":   COLOR_INFO,
    "debug":   COLOR_TEXT_SECONDARY,
    "default": COLOR_TEXT_SECONDARY,
}


class LogConsole(ctk.CTkFrame):
    """A read-only, auto-scrolling log console with colored lines."""

    def __init__(self, master, max_lines: int = 2000, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8, **kwargs)
        self._max_lines = max_lines
        self._line_count = 0
        self._filter_level: str | None = None
        self._all_lines: list[tuple[str, str]] = []  # (level, text)

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        toolbar.pack_propagate(False)

        ctk.CTkLabel(toolbar, text="Console Output",
                     font=ctk.CTkFont("Consolas", 11, "bold"),
                     text_color=COLOR_TEXT_SECONDARY).pack(side="left")

        self._filter_var = ctk.StringVar(value="All")
        filter_menu = ctk.CTkOptionMenu(
            toolbar, variable=self._filter_var,
            values=["All", "Errors", "Warnings", "Info"],
            width=90, height=24,
            fg_color="#21262d", button_color="#388bfd",
            font=ctk.CTkFont("Consolas", 10),
            command=self._on_filter_change
        )
        filter_menu.pack(side="right", padx=(4, 0))

        clear_btn = ctk.CTkButton(
            toolbar, text="Clear", width=50, height=24,
            fg_color="#21262d", hover_color="#30363d",
            font=ctk.CTkFont("Consolas", 10),
            command=self.clear
        )
        clear_btn.pack(side="right", padx=(4, 0))

        # Text widget in a frame
        text_frame = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=6)
        text_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._text = tk.Text(
            text_frame,
            bg="#0d1117", fg=COLOR_TEXT_PRIMARY,
            font=("Consolas", 10),
            state="disabled",
            wrap="word",
            relief="flat", bd=0,
            padx=8, pady=4,
            selectbackground="#388bfd",
            insertbackground=COLOR_TEXT_PRIMARY,
        )
        scrollbar = ctk.CTkScrollbar(text_frame, command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._text.pack(side="left", fill="both", expand=True)

        # Configure color tags
        for level, color in LEVEL_COLORS.items():
            self._text.tag_configure(level, foreground=color)

    def append(self, text: str, level: str = "default") -> None:
        """Append a line to the console."""
        self._all_lines.append((level, text))
        if len(self._all_lines) > self._max_lines:
            self._all_lines.pop(0)

        if self._filter_level and level not in ("default", self._filter_level):
            return

        self._text.configure(state="normal")
        self._text.insert("end", text + "\n", level)
        self._line_count += 1

        # Trim if too many lines
        if self._line_count > self._max_lines:
            self._text.delete("1.0", "2.0")
            self._line_count -= 1

        self._text.configure(state="disabled")
        self._text.see("end")

    def append_payload(self, payload: dict | str) -> None:
        """Accept EventBus payload (dict with level/text or plain string)."""
        if isinstance(payload, dict):
            self.append(payload.get("text", str(payload)), payload.get("level", "default"))
        else:
            self.append(str(payload))

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
        self._line_count = 0
        self._all_lines.clear()

    def _on_filter_change(self, choice: str) -> None:
        level_map = {"All": None, "Errors": "error", "Warnings": "warning", "Info": "info"}
        self._filter_level = level_map.get(choice)
        self._redraw()

    def _redraw(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._line_count = 0
        for level, text in self._all_lines:
            if self._filter_level is None or level == self._filter_level:
                self._text.insert("end", text + "\n", level)
                self._line_count += 1
        self._text.configure(state="disabled")
        self._text.see("end")
