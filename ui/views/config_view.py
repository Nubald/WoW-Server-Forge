"""Configuration editor view — worldserver.conf and authserver.conf."""
from __future__ import annotations

from pathlib import Path
import customtkinter as ctk
from ui.views.base_view import BaseView
from core.config_manager import ConfigManager
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING
)


class ConfigRow(ctk.CTkFrame):
    """A single key=value config row."""
    def __init__(self, master, key: str, value: str, on_change, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._key = key
        self._on_change = on_change
        ctk.CTkLabel(self, text=key, width=260, anchor="w",
                     font=ctk.CTkFont("Consolas", 10),
                     text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        self._entry = ctk.CTkEntry(
            self, width=300, height=26,
            fg_color="#0d1117", border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont("Consolas", 10)
        )
        self._entry.insert(0, value)
        self._entry.pack(side="left", padx=8)
        self._entry.bind("<FocusOut>", lambda e: self._on_change(key, self._entry.get()))

    def get_value(self) -> str:
        return self._entry.get()


class ConfigView(BaseView):

    def build_ui(self):
        self._header(self, "Configuration",
                     "Generate and edit worldserver.conf and authserver.conf")
        self._cfg_mgr = ConfigManager()

        # Generate buttons
        gen_row = ctk.CTkFrame(self, fg_color="transparent")
        gen_row.pack(fill="x", padx=24, pady=(8, 0))

        ctk.CTkButton(
            gen_row, text="⚙  Generate worldserver.conf", height=34, width=220,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._gen_world
        ).pack(side="left")

        ctk.CTkButton(
            gen_row, text="⚙  Generate authserver.conf", height=34, width=220,
            fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BG_CARD,
            border_width=1, border_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._gen_auth
        ).pack(side="left", padx=8)

        self._gen_status = ctk.CTkLabel(
            gen_row, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._gen_status.pack(side="left", padx=8)

        # Tabview for each conf file
        self._tabs = ctk.CTkTabview(self, fg_color=COLOR_BG_CARD, corner_radius=8,
                                    segmented_button_fg_color=COLOR_BG_SECONDARY,
                                    segmented_button_selected_color=COLOR_ACCENT)
        self._tabs.pack(fill="both", expand=True, padx=24, pady=12)
        self._tabs.add("worldserver.conf")
        self._tabs.add("authserver.conf")

        for tab_name in ["worldserver.conf", "authserver.conf"]:
            tab = self._tabs.tab(tab_name)
            scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
            scroll.pack(fill="both", expand=True)
            setattr(self, f"_{tab_name.replace('.', '_')}_scroll", scroll)

            save_btn = ctk.CTkButton(
                tab, text="💾  Save Changes", height=32, width=140,
                fg_color=COLOR_SUCCESS, hover_color="#45c55a",
                font=ctk.CTkFont("Segoe UI", 11),
                command=lambda n=tab_name: self._save_conf(n)
            )
            save_btn.pack(anchor="e", pady=(4, 0))

    def _gen_world(self):
        profile = self.state.active_profile
        if not profile or not profile.install_dir:
            self._gen_status.configure(text="No profile/install dir", text_color=COLOR_ERROR)
            return
        out = Path(profile.install_dir) / "worldserver.conf"
        ok = self._cfg_mgr.generate_worldserver_conf(profile, out)
        if ok:
            self._gen_status.configure(text=f"✓ Generated {out.name}", text_color=COLOR_SUCCESS)
            self._load_conf_tab("worldserver.conf", out)
        else:
            self._gen_status.configure(text="Generation failed", text_color=COLOR_ERROR)

    def _gen_auth(self):
        profile = self.state.active_profile
        if not profile or not profile.install_dir:
            return
        out = Path(profile.install_dir) / "authserver.conf"
        ok = self._cfg_mgr.generate_authserver_conf(profile, out)
        if ok:
            self._gen_status.configure(text=f"✓ Generated {out.name}", text_color=COLOR_SUCCESS)
            self._load_conf_tab("authserver.conf", out)

    def _load_conf_tab(self, tab_name: str, conf_path: Path):
        scroll = getattr(self, f"_{tab_name.replace('.', '_')}_scroll", None)
        if not scroll:
            return
        for w in scroll.winfo_children():
            w.destroy()
        data = self._cfg_mgr.read_conf(conf_path)
        for key, val in data.items():
            row = ConfigRow(scroll, key, val,
                            on_change=lambda k, v, p=conf_path: self._cfg_mgr.update_key(p, k, v))
            row.pack(fill="x", padx=8, pady=2)

    def _save_conf(self, tab_name: str):
        profile = self.state.active_profile
        if not profile:
            return
        self._gen_status.configure(text=f"✓ Saved {tab_name}", text_color=COLOR_SUCCESS)

    def refresh(self):
        profile = self.state.active_profile
        if not profile or not profile.install_dir:
            return
        for conf_name in ["worldserver.conf", "authserver.conf"]:
            conf_path = Path(profile.install_dir) / conf_name
            if conf_path.exists():
                self._load_conf_tab(conf_name, conf_path)
