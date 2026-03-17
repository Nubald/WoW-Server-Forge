"""Source code management view — clone and update the server repo."""
from __future__ import annotations

from pathlib import Path
import customtkinter as ctk
from ui.views.base_view import BaseView
from ui.widgets.log_console import LogConsole
from core.source_manager import SourceManager
from services.worker_service import get_workers
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR
)


class SourceView(BaseView):

    def build_ui(self):
        self._header(self, "Source Code", "Clone or update the server emulator repository")
        self._source_mgr = SourceManager()

        # Info panel
        info = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        info.pack(fill="x", padx=24, pady=(8, 0))

        info_inner = ctk.CTkFrame(info, fg_color="transparent")
        info_inner.pack(fill="x", padx=14, pady=10)

        self._repo_lbl = ctk.CTkLabel(info_inner, text="Repository: —",
                                      font=ctk.CTkFont("Consolas", 11),
                                      text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self._repo_lbl.pack(anchor="w")
        self._branch_lbl = ctk.CTkLabel(info_inner, text="Branch: —",
                                        font=ctk.CTkFont("Consolas", 11),
                                        text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self._branch_lbl.pack(anchor="w")
        self._commit_lbl = ctk.CTkLabel(info_inner, text="Local commit: —",
                                        font=ctk.CTkFont("Consolas", 11),
                                        text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self._commit_lbl.pack(anchor="w")

        # Path row
        path_row = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, corner_radius=8)
        path_row.pack(fill="x", padx=24, pady=12)
        ctk.CTkLabel(path_row, text="Source Directory:",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=14, pady=10)
        self._path_entry = ctk.CTkEntry(
            path_row, width=380, height=30,
            fg_color="#0d1117", border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont("Consolas", 10)
        )
        self._path_entry.pack(side="left", padx=8, pady=8)

        browse_btn = ctk.CTkButton(
            path_row, text="Browse", width=70, height=28,
            fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._browse_path
        )
        browse_btn.pack(side="left", padx=(0, 8))

        # Action buttons
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=(0, 8))

        self._clone_btn = ctk.CTkButton(
            actions, text="⬇  Clone Repository", height=36, width=180,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._clone
        )
        self._clone_btn.pack(side="left")

        self._update_btn = ctk.CTkButton(
            actions, text="⟳  Pull Updates", height=36, width=150,
            fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BG_CARD,
            border_width=1, border_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._update
        )
        self._update_btn.pack(side="left", padx=8)

        self._next_btn = ctk.CTkButton(
            actions, text="Next: Modules  →", height=36, width=160,
            fg_color=COLOR_SUCCESS, hover_color="#45c55a",
            font=ctk.CTkFont("Segoe UI", 12),
            state="disabled",
            command=lambda: self.app.show_view("modules")
        )
        self._next_btn.pack(side="right")

        # Log console
        self._log = LogConsole(self)
        self._log.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    def refresh(self):
        profile = self.state.active_profile
        if not profile:
            return
        sdef = self.app.get_server_def(profile.server_id)
        if sdef:
            repo = sdef.get("repo", {})
            self._repo_lbl.configure(text=f"Repository: {repo.get('url', '—')}")
            self._branch_lbl.configure(text=f"Branch: {repo.get('branch', '—')}")

        source_dir = Path(profile.workspace_dir) / "source"
        if not self._path_entry.get():
            self._path_entry.delete(0, "end")
            self._path_entry.insert(0, str(source_dir))

        if source_dir.exists() and self._source_mgr.is_repo(source_dir):
            commit = self._source_mgr.get_commit(source_dir)
            self._commit_lbl.configure(text=f"Local commit: {commit}", text_color=COLOR_SUCCESS)
            self._next_btn.configure(state="normal")
        else:
            self._commit_lbl.configure(text="Local commit: not cloned", text_color=COLOR_WARNING)

    def _browse_path(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Select Source Directory")
        if path:
            self._path_entry.delete(0, "end")
            self._path_entry.insert(0, path)

    def _clone(self):
        profile = self.state.active_profile
        if not profile:
            self._log.append("[ERROR] No active profile. Select a server first.", "error")
            return
        sdef = self.app.get_server_def(profile.server_id)
        if not sdef:
            return
        url = sdef["repo"]["url"]
        branch = sdef["repo"]["branch"]
        target = Path(self._path_entry.get() or
                      str(Path(profile.workspace_dir) / "source"))

        self._clone_btn.configure(state="disabled", text="Cloning...")
        self._log.clear()
        get_workers().submit("clone", self._do_clone, url, target, branch)

    def _do_clone(self, url: str, target: Path, branch: str):
        for line in self._source_mgr.clone(url, target, branch):
            self.after(0, lambda l=line: self._log.append(l))
        self.after(0, self._on_clone_done)

    def _on_clone_done(self):
        self._clone_btn.configure(state="normal", text="⬇  Clone Repository")
        self._next_btn.configure(state="normal")
        self.refresh()

    def _update(self):
        path = Path(self._path_entry.get())
        self._update_btn.configure(state="disabled", text="Updating...")
        self._log.clear()
        get_workers().submit("update", self._do_update, path)

    def _do_update(self, path: Path):
        for line in self._source_mgr.update(path):
            self.after(0, lambda l=line: self._log.append(l))
        self.after(0, lambda: self._update_btn.configure(state="normal", text="⟳  Pull Updates"))
        self.after(0, self.refresh)

    def _subscribe_events(self):
        self.bus.subscribe("build.log_line", self._on_log)

    def _unsubscribe_events(self):
        self.bus.unsubscribe("build.log_line", self._on_log)

    def _on_log(self, payload):
        self._log.append_payload(payload)
