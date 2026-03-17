"""Prerequisites detection and installation view."""
from __future__ import annotations

import threading
import customtkinter as ctk
from ui.views.base_view import BaseView
from ui.widgets.log_console import LogConsole
from core.prerequisite_manager import PrerequisiteManager, PrereqResult
from services.worker_service import get_workers
from app.constants import (
    COLOR_BG_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, COLOR_ACCENT,
    COLOR_BG_SECONDARY
)


STATUS_CONFIG = {
    True:  ("✓", COLOR_SUCCESS, "Installed"),
    False: ("✗", COLOR_ERROR,   "Missing"),
    None:  ("◌", COLOR_TEXT_MUTED, "Checking..."),
}


class PrereqRow(ctk.CTkFrame):
    def __init__(self, master, req: dict, on_install, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8, height=52, **kwargs)
        self.pack_propagate(False)
        self.req = req
        self._on_install = on_install

        ctk.CTkFrame(self, fg_color=COLOR_BORDER, width=1).pack(side="left", fill="y")

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14)

        self._icon = ctk.CTkLabel(inner, text="◌", font=ctk.CTkFont("Segoe UI", 16),
                                  text_color=COLOR_TEXT_MUTED, width=24)
        self._icon.pack(side="left")

        name_frame = ctk.CTkFrame(inner, fg_color="transparent")
        name_frame.pack(side="left", fill="y", padx=(10, 0))
        ctk.CTkLabel(name_frame, text=req["display_name"],
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(anchor="w")
        self._ver_lbl = ctk.CTkLabel(name_frame, text=f"Required: {req.get('min_version','—')}+",
                                     font=ctk.CTkFont("Segoe UI", 10),
                                     text_color=COLOR_TEXT_MUTED, anchor="w")
        self._ver_lbl.pack(anchor="w")

        self._status_lbl = ctk.CTkLabel(inner, text="",
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        text_color=COLOR_TEXT_SECONDARY)
        self._status_lbl.pack(side="right", padx=(0, 8))

        self._install_btn = ctk.CTkButton(
            inner, text="Install", width=80, height=28,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 11),
            command=lambda: on_install(req["id"])
        )
        self._install_btn.pack(side="right", padx=(0, 8))
        self._install_btn.pack_forget()  # hidden until needed

    def set_result(self, result: PrereqResult):
        icon, color, label = STATUS_CONFIG[result.installed]
        self._icon.configure(text=icon, text_color=color)
        ver_text = f"Found: {result.version}" if result.version else (result.message or "Not found")
        self._ver_lbl.configure(text=ver_text, text_color=color)
        self._status_lbl.configure(text=label, text_color=color)
        if not result.installed:
            self._install_btn.pack(side="right", padx=(0, 8))
        else:
            self._install_btn.pack_forget()

    def set_installing(self):
        self._icon.configure(text="⟳", text_color=COLOR_WARNING)
        self._status_lbl.configure(text="Installing...", text_color=COLOR_WARNING)
        self._install_btn.configure(state="disabled")


class PrerequisitesView(BaseView):

    def build_ui(self):
        self._header(self, "Prerequisites",
                     "Verify and install all required build dependencies")
        self._manager = PrerequisiteManager()

        # Check All button
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(8, 0))

        self._check_btn = ctk.CTkButton(
            btn_row, text="⟳  Check All", width=140, height=34,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._check_all
        )
        self._check_btn.pack(side="left")

        self._progress_lbl = ctk.CTkLabel(
            btn_row, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._progress_lbl.pack(side="left", padx=12)

        # Requirement rows
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLOR_BG_CARD
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(12, 0))

        self._rows: dict[str, PrereqRow] = {}
        requirements = self._manager.get_requirements()
        for req in requirements:
            row = PrereqRow(scroll, req, on_install=self._install_one)
            row.pack(fill="x", pady=4)
            self._rows[req["id"]] = row

        # Log console for install output
        self._log_console = LogConsole(self, height=160)
        self._log_console.pack(fill="x", padx=24, pady=12)

    def _check_all(self):
        self._check_btn.configure(state="disabled", text="Checking...")
        self._progress_lbl.configure(text="")
        get_workers().submit("prereq_check", self._do_check_all)

    def _do_check_all(self):
        results = self._manager.check_all()
        ok = sum(1 for r in results.values() if r.installed)
        total = len(results)
        self.state.prereq_status = {rid: r.installed for rid, r in results.items()}
        self.after(0, lambda: self._check_btn.configure(state="normal", text="⟳  Check All"))
        self.after(0, lambda: self._progress_lbl.configure(
            text=f"{ok}/{total} installed",
            text_color=COLOR_SUCCESS if ok == total else COLOR_WARNING
        ))

    def _install_one(self, req_id: str):
        if req_id in self._rows:
            self._rows[req_id].set_installing()
        self._log_console.clear()
        get_workers().submit(f"install_{req_id}", self._do_install, req_id)

    def _do_install(self, req_id: str):
        for line in self._manager.install(req_id):
            self.after(0, lambda l=line: self._log_console.append(l))
        # Re-check after install
        result = self._manager.check(req_id)
        if result and req_id in self._rows:
            self.after(0, lambda r=result: self._rows[req_id].set_result(r))

    def _subscribe_events(self):
        self.bus.subscribe("prereq.checked", self._on_prereq_checked)

    def _unsubscribe_events(self):
        self.bus.unsubscribe("prereq.checked", self._on_prereq_checked)

    def _on_prereq_checked(self, result: PrereqResult):
        if result.id in self._rows:
            self._rows[result.id].set_result(result)
