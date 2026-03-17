"""Dashboard / home view — system overview cards."""
from __future__ import annotations

import customtkinter as ctk
from ui.views.base_view import BaseView
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_ACCENT, COLOR_INFO
)


def _card(parent, title: str, accent: str = COLOR_ACCENT) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
    outer = ctk.CTkFrame(parent, fg_color=COLOR_BG_CARD, corner_radius=10)
    # Left accent bar
    bar = ctk.CTkFrame(outer, fg_color=accent, width=4, corner_radius=4)
    bar.pack(side="left", fill="y", padx=(0, 0), pady=0)

    inner = ctk.CTkFrame(outer, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=14, pady=12)

    ctk.CTkLabel(inner, text=title.upper(),
                 font=ctk.CTkFont("Segoe UI", 9, "bold"),
                 text_color=COLOR_TEXT_MUTED, anchor="w").pack(anchor="w")
    return outer, inner


class DashboardView(BaseView):

    def build_ui(self):
        self._header(self, "Dashboard", "Overview of your server forge environment")

        # 2×2 card grid
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=24, pady=16)
        grid.columnconfigure((0, 1), weight=1)

        # ── Prerequisite card ─────────────────────────────────────────
        outer, inner = _card(grid, "Prerequisites", COLOR_ACCENT)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        self._prereq_icon = ctk.CTkLabel(inner, text="◌", font=ctk.CTkFont("Segoe UI", 28),
                                         text_color=COLOR_TEXT_MUTED)
        self._prereq_icon.pack(anchor="w")
        self._prereq_lbl = ctk.CTkLabel(inner, text="Checking...",
                                        font=ctk.CTkFont("Segoe UI", 12),
                                        text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self._prereq_lbl.pack(anchor="w")

        # ── Source card ───────────────────────────────────────────────
        outer, inner = _card(grid, "Source Code", COLOR_INFO)
        outer.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        self._source_icon = ctk.CTkLabel(inner, text="◌", font=ctk.CTkFont("Segoe UI", 28),
                                         text_color=COLOR_TEXT_MUTED)
        self._source_icon.pack(anchor="w")
        self._source_lbl = ctk.CTkLabel(inner, text="No source cloned yet",
                                        font=ctk.CTkFont("Segoe UI", 12),
                                        text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self._source_lbl.pack(anchor="w")

        # ── Build card ────────────────────────────────────────────────
        outer, inner = _card(grid, "Last Build", COLOR_WARNING)
        outer.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(8, 0))
        self._build_icon = ctk.CTkLabel(inner, text="◌", font=ctk.CTkFont("Segoe UI", 28),
                                        text_color=COLOR_TEXT_MUTED)
        self._build_icon.pack(anchor="w")
        self._build_lbl = ctk.CTkLabel(inner, text="Never compiled",
                                       font=ctk.CTkFont("Segoe UI", 12),
                                       text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self._build_lbl.pack(anchor="w")

        # ── Server card ───────────────────────────────────────────────
        outer, inner = _card(grid, "Server Status", COLOR_SUCCESS)
        outer.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(8, 0))
        self._server_icon = ctk.CTkLabel(inner, text="◌", font=ctk.CTkFont("Segoe UI", 28),
                                         text_color=COLOR_TEXT_MUTED)
        self._server_icon.pack(anchor="w")
        self._server_lbl = ctk.CTkLabel(inner, text="Auth: Offline  |  World: Offline",
                                        font=ctk.CTkFont("Segoe UI", 12),
                                        text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self._server_lbl.pack(anchor="w")

        # ── Active profile strip ──────────────────────────────────────
        profile_strip = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        profile_strip.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(profile_strip, text="Active Profile",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=COLOR_TEXT_MUTED).pack(side="left", padx=14, pady=10)
        self._profile_lbl = ctk.CTkLabel(profile_strip, text="None",
                                         font=ctk.CTkFont("Segoe UI", 12),
                                         text_color=COLOR_TEXT_PRIMARY)
        self._profile_lbl.pack(side="left")

        new_btn = ctk.CTkButton(
            profile_strip, text="+ New Profile", width=120, height=28,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._new_profile
        )
        new_btn.pack(side="right", padx=14, pady=8)

        # ── Quick action buttons ──────────────────────────────────────
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=(0, 16))

        for label, view_id, color in [
            ("⚙  Check Prerequisites", "prerequisites", COLOR_ACCENT),
            ("▶  Compile Server",       "build",         "#3fb950"),
            ("◉  Control Panel",        "control",       "#d29922"),
            ("⬇  Client Info",          "client",        "#8b949e"),
        ]:
            ctk.CTkButton(
                actions, text=label, height=38,
                fg_color=COLOR_BG_CARD, hover_color=COLOR_BG_SECONDARY,
                border_width=1, border_color=COLOR_BORDER,
                text_color=COLOR_TEXT_PRIMARY,
                font=ctk.CTkFont("Segoe UI", 12),
                corner_radius=8,
                command=lambda vid=view_id: self.app.show_view(vid)
            ).pack(side="left", expand=True, fill="x", padx=(0, 8))

    def refresh(self):
        profile = self.state.active_profile
        if profile:
            self._profile_lbl.configure(text=f"{profile.name}  ({profile.server_id})")
        else:
            self._profile_lbl.configure(text="No profile — click '+ New Profile' to start")

    def _subscribe_events(self):
        self.bus.subscribe("prereq.checked",         self._on_prereq_update)
        self.bus.subscribe("process.status_changed", self._on_process_status)
        self.bus.subscribe("build.complete",         self._on_build_complete)

    def _unsubscribe_events(self):
        self.bus.unsubscribe("prereq.checked",         self._on_prereq_update)
        self.bus.unsubscribe("process.status_changed", self._on_process_status)
        self.bus.unsubscribe("build.complete",         self._on_build_complete)

    def _on_prereq_update(self, _payload):
        status = self.state.prereq_status
        if not status:
            return
        all_ok = all(status.values())
        some_ok = any(status.values())
        if all_ok:
            self._prereq_icon.configure(text="✓", text_color=COLOR_SUCCESS)
            self._prereq_lbl.configure(text="All prerequisites satisfied", text_color=COLOR_SUCCESS)
        elif some_ok:
            failed = sum(1 for v in status.values() if not v)
            self._prereq_icon.configure(text="⚠", text_color=COLOR_WARNING)
            self._prereq_lbl.configure(text=f"{failed} prerequisite(s) missing",
                                        text_color=COLOR_WARNING)
        else:
            self._prereq_icon.configure(text="✗", text_color=COLOR_ERROR)
            self._prereq_lbl.configure(text="Prerequisites not checked", text_color=COLOR_ERROR)

    def _on_process_status(self, payload: dict):
        server = payload.get("server", "")
        status = payload.get("status", "stopped")
        running = status == "running"
        auth_run = self.state.server_status.get("auth") == "running"
        world_run = self.state.server_status.get("world") == "running"
        if running:
            self.state.server_status[server] = "running"
        else:
            self.state.server_status[server] = status
        auth_run = self.state.server_status.get("auth") == "running"
        world_run = self.state.server_status.get("world") == "running"
        if auth_run and world_run:
            self._server_icon.configure(text="●", text_color=COLOR_SUCCESS)
        elif auth_run or world_run:
            self._server_icon.configure(text="◐", text_color=COLOR_WARNING)
        else:
            self._server_icon.configure(text="○", text_color=COLOR_TEXT_MUTED)
        self._server_lbl.configure(
            text=f"Auth: {'Online' if auth_run else 'Offline'}  |  "
                 f"World: {'Online' if world_run else 'Offline'}"
        )

    def _on_build_complete(self, result):
        if hasattr(result, "success"):
            ok = result.success
        elif isinstance(result, dict):
            ok = result.get("success", False)
        else:
            ok = False
        if ok:
            self._build_icon.configure(text="✓", text_color=COLOR_SUCCESS)
            self._build_lbl.configure(text="Last build: SUCCESS", text_color=COLOR_SUCCESS)
        else:
            self._build_icon.configure(text="✗", text_color=COLOR_ERROR)
            self._build_lbl.configure(text="Last build: FAILED", text_color=COLOR_ERROR)

    def _new_profile(self):
        self.app.show_view("server_select")
