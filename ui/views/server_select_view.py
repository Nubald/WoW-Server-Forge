"""Server / core selection view — choose expansion and emulator."""
from __future__ import annotations

import json
from pathlib import Path
import customtkinter as ctk
from ui.views.base_view import BaseView
from models.server_profile import ServerProfile, DbConfig, NetworkConfig
from app.constants import (
    SERVERS_DIR, COLOR_BG_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_BG_SECONDARY,
    COLOR_SUCCESS
)

EXPANSION_LABELS = {
    "vanilla":      "Classic (1.12.1)",
    "tbc":          "The Burning Crusade (2.4.3)",
    "wotlk":        "Wrath of the Lich King (3.3.5a)",
    "cata":         "Cataclysm (4.3.4)",
    "mop":          "Mists of Pandaria (5.4.8)",
    "wod":          "Warlords of Draenor (6.2.4)",
    "legion":       "Legion (7.3.5)",
    "bfa":          "Battle for Azeroth (8.3.7)",
    "shadowlands":  "Shadowlands (9.2.7)",
    "dragonflight": "Dragonflight (10.x)",
}


class ServerCard(ctk.CTkFrame):
    def __init__(self, master, server_def: dict, on_select, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=10,
                         cursor="hand2", **kwargs)
        self._server_def = server_def
        self._on_select = on_select
        self._selected = False
        accent = server_def.get("color_accent", COLOR_ACCENT)

        # Left accent bar
        self._bar = ctk.CTkFrame(self, fg_color=accent, width=5, corner_radius=0)
        self._bar.pack(side="left", fill="y")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=12)

        # Expansion badge
        exp = server_def.get("expansion", "")
        exp_label = EXPANSION_LABELS.get(exp, exp.upper())
        badge = ctk.CTkLabel(body, text=exp_label.upper(),
                             font=ctk.CTkFont("Segoe UI", 8, "bold"),
                             text_color=accent,
                             fg_color=COLOR_BG_SECONDARY,
                             corner_radius=4, padx=6, pady=2)
        badge.pack(anchor="w")

        ctk.CTkLabel(body, text=server_def.get("display_name", ""),
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(body, text=f"WoW {server_def.get('wow_version','')}  •  {server_def.get('short_name','')}",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(anchor="w")

        # Repo + notes
        branch = server_def.get("repo", {}).get("branch", "")
        ctk.CTkLabel(body, text=f"Branch: {branch}",
                     font=ctk.CTkFont("Consolas", 9),
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(anchor="w", pady=(4, 0))

        notes = server_def.get("notes", "")
        if notes:
            ctk.CTkLabel(body, text=notes,
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=COLOR_TEXT_MUTED, anchor="w",
                         wraplength=240, justify="left").pack(anchor="w", pady=(2, 0))

        # Select button
        self._btn = ctk.CTkButton(
            body, text="Select", width=90, height=28,
            fg_color=accent, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._select
        )
        self._btn.pack(anchor="e", pady=(6, 0))

        self.bind("<Button-1>", lambda e: self._select())
        for widget in (body, badge):
            widget.bind("<Button-1>", lambda e: self._select())

    def _select(self):
        self._on_select(self._server_def)

    def set_selected(self, selected: bool):
        self._selected = selected
        color = COLOR_SUCCESS if selected else COLOR_BORDER
        self.configure(border_width=2 if selected else 1, border_color=color)
        self._btn.configure(text="✓ Selected" if selected else "Select")


class ServerSelectView(BaseView):

    def build_ui(self):
        self._header(self, "Select Server Core",
                     "Choose the expansion and emulator for your private server")
        self._server_defs = self._load_server_defs()
        self._selected_id: str | None = None
        self._cards: dict[str, ServerCard] = {}

        # Profile name input
        name_row = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        name_row.pack(fill="x", padx=24, pady=(8, 0))
        ctk.CTkLabel(name_row, text="Profile Name:",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=14, pady=10)
        self._name_entry = ctk.CTkEntry(
            name_row, placeholder_text="My WoW Server",
            width=260, height=30,
            fg_color="#0d1117", border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY
        )
        self._name_entry.pack(side="left", padx=8, pady=8)

        # Expansion filter
        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=24, pady=(8, 0))
        ctk.CTkLabel(filter_row, text="Filter by expansion:",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY).pack(side="left")

        self._filter_var = ctk.StringVar(value="All")
        exp_options = ["All"] + list(EXPANSION_LABELS.keys())
        ctk.CTkOptionMenu(
            filter_row, variable=self._filter_var,
            values=exp_options,
            width=240, height=28,
            fg_color="#21262d", button_color=COLOR_ACCENT,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._apply_filter
        ).pack(side="left", padx=8)

        ctk.CTkLabel(filter_row, text="",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COLOR_TEXT_MUTED).pack(side="left", padx=4)
        self._count_lbl = ctk.CTkLabel(
            filter_row, text=f"{len(self._server_defs)} cores available",
            font=ctk.CTkFont("Segoe UI", 10), text_color=COLOR_TEXT_MUTED
        )
        self._count_lbl.pack(side="left")

        # Server cards grid
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=24, pady=12)
        self._scroll.columnconfigure((0, 1), weight=1)

        self._render_cards(self._server_defs)

        # Create profile button
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 16))
        self._create_btn = ctk.CTkButton(
            btn_row, text="Create Profile  →", height=38, width=160,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 13),
            state="disabled",
            command=self._create_profile
        )
        self._create_btn.pack(side="right")

    def _render_cards(self, defs: list[dict]) -> None:
        # Destroy existing cards
        for w in self._scroll.winfo_children():
            w.destroy()
        self._cards = {}
        row_idx = 0
        col_idx = 0
        for sdef in defs:
            card = ServerCard(self._scroll, sdef, on_select=self._on_select)
            card.grid(row=row_idx, column=col_idx, sticky="nsew",
                      padx=(0 if col_idx == 0 else 8, 0), pady=(0, 12))
            self._cards[sdef["id"]] = card
            # Re-apply selection highlight if this card was previously selected
            if sdef["id"] == self._selected_id:
                card.set_selected(True)
            col_idx += 1
            if col_idx >= 2:
                col_idx = 0
                row_idx += 1
        self._count_lbl.configure(text=f"{len(defs)} core{'s' if len(defs) != 1 else ''} shown")

    def _apply_filter(self, value: str) -> None:
        if value == "All":
            filtered = self._server_defs
        else:
            filtered = [s for s in self._server_defs if s.get("expansion") == value]
        self._render_cards(filtered)

    def _load_server_defs(self) -> list[dict]:
        defs = []
        if SERVERS_DIR.exists():
            for f in sorted(SERVERS_DIR.glob("*.json")):
                try:
                    defs.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    pass
        return defs

    def _on_select(self, server_def: dict):
        for card in self._cards.values():
            card.set_selected(False)
        sid = server_def["id"]
        self._selected_id = sid
        if sid in self._cards:
            self._cards[sid].set_selected(True)
        self._create_btn.configure(state="normal")

    def _create_profile(self):
        if not self._selected_id:
            return
        name = self._name_entry.get().strip() or "My WoW Server"
        sdef = next((s for s in self._server_defs if s["id"] == self._selected_id), None)
        if not sdef:
            return

        profile = ServerProfile(
            name=name,
            server_id=self._selected_id,
            workspace_dir=str(Path.home() / "WowServer" / name.replace(" ", "_")),
        )
        profile.build_dir = str(Path(profile.workspace_dir) / "build")
        profile.install_dir = str(Path(profile.workspace_dir) / "install")

        self.state.active_profile = profile
        profile.save(self.app.profiles_dir)
        self.app.status_bar.set_profile(name)
        self.app.show_view("source")
