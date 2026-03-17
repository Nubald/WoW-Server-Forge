"""Module manager view — enable/disable mods like Eluna, NPC Bots, etc."""
from __future__ import annotations

import customtkinter as ctk
from ui.views.base_view import BaseView
from ui.widgets.log_console import LogConsole
from core.module_manager import ModuleManager
from models.module_definition import ModuleDefinition
from services.worker_service import get_workers
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR
)

TAG_COLORS = {
    "gameplay":     "#1a73e8",
    "bots":         "#9333ea",
    "solo-friendly":"#16a34a",
    "scripting":    "#d97706",
    "economy":      "#0891b2",
    "combat":       "#dc2626",
}


class ModuleCard(ctk.CTkFrame):
    def __init__(self, master, mod: ModuleDefinition, on_toggle, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=10, **kwargs)
        self._mod = mod
        self._enabled = False
        self._on_toggle = on_toggle

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # Header row
        hdr = ctk.CTkFrame(body, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=mod.display_name,
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(side="left")

        self._toggle = ctk.CTkSwitch(
            hdr, text="", width=46, height=22,
            onvalue=True, offvalue=False,
            progress_color=COLOR_ACCENT,
            command=self._on_click
        )
        self._toggle.pack(side="right")

        # Description
        ctk.CTkLabel(body, text=mod.description,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COLOR_TEXT_SECONDARY, anchor="w",
                     wraplength=300).pack(anchor="w", pady=(4, 0))

        # Author & tags
        meta = ctk.CTkFrame(body, fg_color="transparent")
        meta.pack(fill="x", pady=(6, 0))
        if mod.author:
            ctk.CTkLabel(meta, text=f"by {mod.author}",
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=COLOR_TEXT_MUTED).pack(side="left")

        for tag in mod.tags[:3]:
            color = TAG_COLORS.get(tag, COLOR_TEXT_MUTED)
            ctk.CTkLabel(meta, text=tag,
                         font=ctk.CTkFont("Segoe UI", 8, "bold"),
                         text_color=color,
                         fg_color=COLOR_BG_SECONDARY,
                         corner_radius=4, padx=5, pady=2).pack(side="right", padx=2)

        # Warning
        if mod.warning:
            warn_frame = ctk.CTkFrame(body, fg_color="#2d1f00", corner_radius=6)
            warn_frame.pack(fill="x", pady=(6, 0))
            ctk.CTkLabel(warn_frame, text=f"⚠  {mod.warning}",
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=COLOR_WARNING).pack(padx=8, pady=4)

    def _on_click(self):
        self._enabled = self._toggle.get()
        self._on_toggle(self._mod.id, self._enabled)
        self.configure(border_width=2 if self._enabled else 0,
                       border_color=COLOR_ACCENT if self._enabled else "transparent")

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if enabled:
            self._toggle.select()
            self.configure(border_width=2, border_color=COLOR_ACCENT)
        else:
            self._toggle.deselect()
            self.configure(border_width=0)


class ModulesView(BaseView):

    def build_ui(self):
        self._header(self, "Module Manager",
                     "Add extra features to your server (Eluna, NPC Bots, and more)")
        self._mgr = ModuleManager()

        # Stats row
        stats = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        stats.pack(fill="x", padx=24, pady=(8, 0))
        self._stats_lbl = ctk.CTkLabel(stats, text="0 modules enabled",
                                       font=ctk.CTkFont("Segoe UI", 11),
                                       text_color=COLOR_TEXT_SECONDARY)
        self._stats_lbl.pack(side="left", padx=14, pady=8)

        apply_btn = ctk.CTkButton(
            stats, text="Apply to Source  →", width=160, height=28,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._apply_modules
        )
        apply_btn.pack(side="right", padx=14, pady=8)

        # Module grid
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=24, pady=12)
        self._scroll.columnconfigure((0, 1), weight=1)

        self._cards: dict[str, ModuleCard] = {}
        self._refresh_cards()

        # Log console
        self._log = LogConsole(self, height=140)
        self._log.pack(fill="x", padx=24, pady=(0, 16))

    def _refresh_cards(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._cards.clear()

        profile = self.state.active_profile
        server_id = profile.server_id if profile else ""
        mods = self._mgr.get_compatible(server_id) if server_id else list(self._mgr.get_all().values())

        row_i = 0
        col_i = 0
        for mod in mods:
            card = ModuleCard(self._scroll, mod, on_toggle=self._on_toggle)
            card.grid(row=row_i, column=col_i, sticky="nsew",
                      padx=(0 if col_i == 0 else 8, 0), pady=(0, 10))
            if profile and mod.id in profile.enabled_modules:
                card.set_enabled(True)
            self._cards[mod.id] = card
            col_i += 1
            if col_i >= 2:
                col_i = 0
                row_i += 1

    def _on_toggle(self, mod_id: str, enabled: bool):
        profile = self.state.active_profile
        if not profile:
            return
        if enabled:
            if mod_id not in profile.enabled_modules:
                profile.enabled_modules.append(mod_id)
        else:
            profile.enabled_modules = [m for m in profile.enabled_modules if m != mod_id]

        profile.save(self.app.profiles_dir)
        self._update_stats()

    def _update_stats(self):
        count = len(self.state.active_profile.enabled_modules) if self.state.active_profile else 0
        self._stats_lbl.configure(text=f"{count} module(s) enabled")

    def _apply_modules(self):
        profile = self.state.active_profile
        if not profile:
            self._log.append("[ERROR] No active profile", "error")
            return
        if not profile.enabled_modules:
            self._log.append("[INFO] No modules to apply", "info")
            return
        source_dir = self.app.get_source_dir()
        if not source_dir or not source_dir.exists():
            self._log.append("[ERROR] Source not cloned yet", "error")
            return
        self._log.clear()
        get_workers().submit("apply_modules", self._do_apply, source_dir)

    def _do_apply(self, source_dir):
        profile = self.state.active_profile
        for mod_id in profile.enabled_modules:
            for line in self._mgr.enable_module(mod_id, source_dir):
                self.after(0, lambda l=line: self._log.append(l))

    def refresh(self):
        self._refresh_cards()
        self._update_stats()
