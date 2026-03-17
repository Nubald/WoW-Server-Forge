"""Bottom status bar widget."""
from __future__ import annotations

import customtkinter as ctk
from app.constants import (
    COLOR_BG_SECONDARY, COLOR_BORDER, COLOR_TEXT_SECONDARY,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING
)


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master, height=28, fg_color=COLOR_BG_SECONDARY,
            corner_radius=0, **kwargs
        )
        self.pack_propagate(False)

        # Divider
        ctk.CTkFrame(self, fg_color=COLOR_BORDER, height=1).pack(fill="x", side="top")

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12)

        self._profile_lbl = ctk.CTkLabel(
            inner, text="No profile loaded",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._profile_lbl.pack(side="left")

        # Spacer
        ctk.CTkLabel(inner, text=" | ", text_color=COLOR_BORDER,
                     font=ctk.CTkFont("Segoe UI", 10)).pack(side="left")

        self._build_lbl = ctk.CTkLabel(
            inner, text="Build: —",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._build_lbl.pack(side="left")

        ctk.CTkLabel(inner, text=" | ", text_color=COLOR_BORDER,
                     font=ctk.CTkFont("Segoe UI", 10)).pack(side="left")

        self._auth_lbl = ctk.CTkLabel(
            inner, text="Auth: ●",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._auth_lbl.pack(side="left")

        self._world_lbl = ctk.CTkLabel(
            inner, text="World: ●",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._world_lbl.pack(side="left", padx=(8, 0))

        self._msg_lbl = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._msg_lbl.pack(side="right")

    def set_profile(self, name: str) -> None:
        self._profile_lbl.configure(text=f"Profile: {name}")

    def set_build_status(self, status: str) -> None:
        color_map = {
            "SUCCESS": COLOR_SUCCESS, "FAILED": COLOR_ERROR,
            "BUILDING": COLOR_WARNING, "—": COLOR_TEXT_SECONDARY
        }
        color = color_map.get(status.upper(), COLOR_TEXT_SECONDARY)
        self._build_lbl.configure(text=f"Build: {status}", text_color=color)

    def set_process_status(self, server: str, running: bool) -> None:
        color = COLOR_SUCCESS if running else COLOR_TEXT_SECONDARY
        text = f"  ● {server.capitalize()}: {'Online' if running else 'Offline'}"
        if server == "auth":
            self._auth_lbl.configure(text=text, text_color=color)
        else:
            self._world_lbl.configure(text=text, text_color=color)

    def set_message(self, msg: str) -> None:
        self._msg_lbl.configure(text=msg)
