"""Server control panel view — start, stop, restart auth/worldserver."""
from __future__ import annotations

import time
from pathlib import Path
import customtkinter as ctk
from ui.views.base_view import BaseView
from ui.widgets.log_console import LogConsole
from core.server_process_manager import ServerProcessManager
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING
)


def _fmt_uptime(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class ServerPanel(ctk.CTkFrame):
    """Card for one server process (auth or world)."""

    def __init__(self, master, title: str, server_type: str,
                 on_start, on_stop, on_restart, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=10, **kwargs)
        self._server_type = server_type

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # Title + status badge
        hdr = ctk.CTkFrame(body, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=title, font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=COLOR_TEXT_PRIMARY).pack(side="left")
        self._badge = ctk.CTkLabel(hdr, text="● OFFLINE",
                                   font=ctk.CTkFont("Segoe UI", 10, "bold"),
                                   text_color=COLOR_TEXT_MUTED,
                                   fg_color=COLOR_BG_SECONDARY,
                                   corner_radius=6, padx=8, pady=3)
        self._badge.pack(side="right")

        # Stats
        stats = ctk.CTkFrame(body, fg_color=COLOR_BG_SECONDARY, corner_radius=6)
        stats.pack(fill="x", pady=10)
        stats_inner = ctk.CTkFrame(stats, fg_color="transparent")
        stats_inner.pack(fill="x", padx=10, pady=6)

        for col_idx, (lbl, attr) in enumerate([
            ("Uptime", "_uptime_lbl"),
            ("Memory", "_mem_lbl"),
            ("CPU",    "_cpu_lbl"),
        ]):
            col = ctk.CTkFrame(stats_inner, fg_color="transparent")
            col.pack(side="left", expand=True)
            ctk.CTkLabel(col, text=lbl.upper(),
                         font=ctk.CTkFont("Segoe UI", 8, "bold"),
                         text_color=COLOR_TEXT_MUTED).pack()
            lbl_widget = ctk.CTkLabel(col, text="—",
                                      font=ctk.CTkFont("Consolas", 11),
                                      text_color=COLOR_TEXT_PRIMARY)
            lbl_widget.pack()
            setattr(self, attr, lbl_widget)

        # Buttons
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")

        self._start_btn = ctk.CTkButton(
            btn_row, text="▶ Start", height=34, width=90,
            fg_color=COLOR_SUCCESS, hover_color="#45c55a",
            font=ctk.CTkFont("Segoe UI", 12),
            command=on_start
        )
        self._start_btn.pack(side="left")

        self._stop_btn = ctk.CTkButton(
            btn_row, text="■ Stop", height=34, width=90,
            fg_color=COLOR_ERROR, hover_color="#ff6b6b",
            font=ctk.CTkFont("Segoe UI", 12),
            state="disabled",
            command=on_stop
        )
        self._stop_btn.pack(side="left", padx=6)

        self._restart_btn = ctk.CTkButton(
            btn_row, text="⟳ Restart", height=34, width=90,
            fg_color=COLOR_WARNING, hover_color="#e5b025",
            font=ctk.CTkFont("Segoe UI", 12),
            state="disabled",
            command=on_restart
        )
        self._restart_btn.pack(side="left", padx=6)

    def set_status(self, status: str):
        configs = {
            "running":  ("● ONLINE",  COLOR_SUCCESS, True),
            "starting": ("⟳ STARTING", COLOR_WARNING, False),
            "stopped":  ("● OFFLINE", COLOR_TEXT_MUTED, False),
            "crashed":  ("✗ CRASHED", COLOR_ERROR, False),
            "error":    ("✗ ERROR",   COLOR_ERROR, False),
        }
        text, color, running = configs.get(status, ("● OFFLINE", COLOR_TEXT_MUTED, False))
        self._badge.configure(text=text, text_color=color)
        self._start_btn.configure(state="disabled" if running else "normal")
        self._stop_btn.configure(state="normal" if running else "disabled")
        self._restart_btn.configure(state="normal" if running else "disabled")
        self.configure(border_width=2 if running else 0,
                       border_color=COLOR_SUCCESS if running else "transparent")

    def update_stats(self, uptime: float, memory_mb: float, cpu: float):
        self._uptime_lbl.configure(text=_fmt_uptime(uptime))
        self._mem_lbl.configure(text=f"{memory_mb:.0f} MB")
        self._cpu_lbl.configure(text=f"{cpu:.1f}%")


class ControlView(BaseView):

    def build_ui(self):
        self._header(self, "Server Control Panel",
                     "Start, stop, and monitor your auth and world servers")
        self._proc_mgr = ServerProcessManager()

        # Two server panels side by side
        panels = ctk.CTkFrame(self, fg_color="transparent")
        panels.pack(fill="x", padx=24, pady=(8, 0))
        panels.columnconfigure((0, 1), weight=1)

        self._auth_panel = ServerPanel(
            panels, "Auth Server", "auth",
            on_start=lambda: self._start("auth"),
            on_stop=lambda: self._stop("auth"),
            on_restart=lambda: self._restart("auth")
        )
        self._auth_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self._world_panel = ServerPanel(
            panels, "World Server", "world",
            on_start=lambda: self._start("world"),
            on_stop=lambda: self._stop("world"),
            on_restart=lambda: self._restart("world")
        )
        self._world_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # Quick command input
        cmd_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        cmd_frame.pack(fill="x", padx=24, pady=12)
        cmd_inner = ctk.CTkFrame(cmd_frame, fg_color="transparent")
        cmd_inner.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(cmd_inner, text="Console Command:",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY).pack(side="left")

        self._cmd_entry = ctk.CTkEntry(
            cmd_inner, width=340, height=30, placeholder_text=".server info",
            fg_color="#0d1117", border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont("Consolas", 11)
        )
        self._cmd_entry.pack(side="left", padx=8)
        self._cmd_entry.bind("<Return>", lambda e: self._send_command())

        self._server_sel = ctk.StringVar(value="world")
        ctk.CTkOptionMenu(
            cmd_inner, variable=self._server_sel,
            values=["world", "auth"], width=80, height=30,
            fg_color="#21262d", button_color=COLOR_ACCENT
        ).pack(side="left", padx=4)

        ctk.CTkButton(cmd_inner, text="Send", width=70, height=28,
                      fg_color=COLOR_ACCENT, hover_color="#58a6ff",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=self._send_command).pack(side="left", padx=4)

        # Server log
        self._log = LogConsole(self)
        self._log.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    def _get_exe(self, server_type: str) -> Path | None:
        profile = self.state.active_profile
        if not profile:
            return None
        sdef = self.app.get_server_def(profile.server_id) or {}
        exes = sdef.get("executables", {})
        exe_name = exes.get(server_type + "server", f"{server_type}server.exe")
        return Path(profile.install_dir) / exe_name

    def _start(self, server_type: str):
        exe = self._get_exe(server_type)
        if not exe:
            self._log.append(f"[ERROR] No profile or server selected", "error")
            return
        profile = self.state.active_profile
        working_dir = Path(profile.install_dir)
        self._log.append(f"[INFO] Starting {server_type}server: {exe}", "info")
        panel = self._auth_panel if server_type == "auth" else self._world_panel
        panel.set_status("starting")
        self._proc_mgr.start(server_type, exe, working_dir)

    def _stop(self, server_type: str):
        self._proc_mgr.stop(server_type)
        panel = self._auth_panel if server_type == "auth" else self._world_panel
        panel.set_status("stopped")
        self.app.status_bar.set_process_status(server_type, False)

    def _restart(self, server_type: str):
        exe = self._get_exe(server_type)
        if not exe:
            return
        profile = self.state.active_profile
        working_dir = Path(profile.install_dir)
        self._proc_mgr.restart(server_type, exe, working_dir)

    def _send_command(self):
        cmd = self._cmd_entry.get().strip()
        server = self._server_sel.get()
        if cmd:
            self._proc_mgr.send_command(server, cmd)
            self._log.append(f"[CMD→{server}] {cmd}", "info")
            self._cmd_entry.delete(0, "end")

    def _subscribe_events(self):
        self.bus.subscribe("process.status_changed", self._on_status)
        self.bus.subscribe("process.stats",          self._on_stats)
        self.bus.subscribe("process.log_line",       self._on_log)

    def _unsubscribe_events(self):
        self.bus.unsubscribe("process.status_changed", self._on_status)
        self.bus.unsubscribe("process.stats",          self._on_stats)
        self.bus.unsubscribe("process.log_line",       self._on_log)

    def _on_status(self, payload: dict):
        server = payload.get("server", "")
        status = payload.get("status", "stopped")
        panel = self._auth_panel if server == "auth" else self._world_panel
        panel.set_status(status)
        self.app.status_bar.set_process_status(server, status == "running")
        self.state.server_status[server] = status

    def _on_stats(self, payload: dict):
        server = payload.get("server", "")
        panel = self._auth_panel if server == "auth" else self._world_panel
        panel.update_stats(
            payload.get("uptime", 0),
            payload.get("memory_mb", 0),
            payload.get("cpu_percent", 0)
        )

    def _on_log(self, payload: dict):
        server = payload.get("server", "")
        line = payload.get("line", "")
        self._log.append(f"[{server.upper()}] {line}")
