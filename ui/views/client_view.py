"""Client info view — realmlist, download links for players, and data extraction."""
from __future__ import annotations

import subprocess
import threading
import webbrowser
from pathlib import Path
import customtkinter as ctk
from ui.views.base_view import BaseView
from ui.widgets.log_console import LogConsole
from services.worker_service import get_workers
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR
)

CLIENT_LINKS = {
    "vanilla": [
        {
            "label": "Vanilla Client 1.12.1",
            "description": "Original Vanilla WoW client for patch 1.12.1-5875. Required for CMaNGOS Classic, MaNGOSZero, and vMaNGOS.",
            "url": "https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/",
            "size": "~4 GB",
            "type": "Community",
        },
        {
            "label": "Turtle WoW Client",
            "description": "Enhanced Vanilla 1.12.1 client with additional patches maintained by the Turtle WoW community.",
            "url": "https://turtle-wow.org/",
            "size": "~5 GB",
            "type": "Community",
        },
    ],
    "tbc": [
        {
            "label": "TBC Client 2.4.3",
            "description": "The Burning Crusade client for patch 2.4.3-8606. Required for CMaNGOS TBC, OregonCore, and MaNGOSOne.",
            "url": "https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/",
            "size": "~6 GB",
            "type": "Community",
        },
        {
            "label": "Atlantiss / Netherwing TBC",
            "description": "TBC 2.4.3 client mirrors distributed by major TBC private server communities.",
            "url": "https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/",
            "size": "~6 GB",
            "type": "Community",
        },
    ],
    "wotlk": [
        {
            "label": "Warmane Client (3.3.5a)",
            "description": "Full WotLK client maintained by Warmane. Patch 3.3.5a-12340. Required for TrinityCore, AzerothCore, CMaNGOS WotLK.",
            "url": "https://www.warmane.com/client",
            "size": "~8 GB",
            "type": "Official Mirror",
        },
        {
            "label": "Wowhead Classic Archive",
            "description": "Client download instructions via the Wowhead community archive.",
            "url": "https://classic.wowhead.com",
            "size": "~8 GB",
            "type": "Community",
        },
        {
            "label": "OwnedCore WotLK Mirrors",
            "description": "Community-maintained patch mirrors for WotLK 3.3.5a-12340.",
            "url": "https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/",
            "size": "~8 GB",
            "type": "Community",
        },
    ],
    "cata": [
        {
            "label": "Cataclysm Client 4.3.4",
            "description": "Cataclysm client for patch 4.3.4-15595. Required for TrinityCore Cata, AzerothCore Cata, and MaNGOSThree.",
            "url": "https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/",
            "size": "~15 GB",
            "type": "Community",
        },
        {
            "label": "Firestorm Cataclysm Client",
            "description": "Cataclysm 4.3.4 client mirror maintained by the Firestorm private server community.",
            "url": "https://firestorm-servers.com/en/client",
            "size": "~15 GB",
            "type": "Community",
        },
    ],
    "mop": [
        {
            "label": "MoP Client 5.4.8",
            "description": "Mists of Pandaria client for patch 5.4.8-18414. Required for SkyFire 5.4.8.",
            "url": "https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/",
            "size": "~20 GB",
            "type": "Community",
        },
        {
            "label": "Firestorm MoP Client",
            "description": "MoP 5.4.8 client as distributed by Firestorm and Dalaran-WoW server communities.",
            "url": "https://firestorm-servers.com/en/client",
            "size": "~20 GB",
            "type": "Community",
        },
    ],
    "wod": [
        {
            "label": "WoD Client 6.2.4",
            "description": "Warlords of Draenor client for patch 6.2.4-21742. Required for TrinityCore 6.x branch.",
            "url": "https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/",
            "size": "~22 GB",
            "type": "Community",
        },
    ],
    "dragonflight": [
        {
            "label": "Official Battle.net Client",
            "description": "TrinityCore master targets the latest live WoW version. Install via the official Blizzard Battle.net app.",
            "url": "https://www.blizzard.com/en-us/apps/battle.net/desktop",
            "size": "~50+ GB",
            "type": "Official",
        },
    ],
}

# Extractor steps in run order
EXTRACTORS = [
    {
        "id": "dbc_maps",
        "label": "DBC + Maps",
        "description": "Extracts DBC data files and terrain maps. Required for server to start.",
        "exe": "mapextractor.exe",
        "args": [],
        "output_dirs": ["dbc", "maps"],
    },
    {
        "id": "vmap_extract",
        "label": "VMaps (extract)",
        "description": "Extracts visual mesh data from MPQ archives for line-of-sight calculations.",
        "exe": "vmap4extractor.exe",
        "args": [],
        "output_dirs": ["Buildings"],
    },
    {
        "id": "vmap_assemble",
        "label": "VMaps (assemble)",
        "description": "Assembles extracted vmap data into the vmaps/ directory.",
        "exe": "vmap4assembler.exe",
        "args": ["Buildings", "vmaps"],
        "output_dirs": ["vmaps"],
    },
    {
        "id": "mmaps",
        "label": "MMaps",
        "description": "Generates movement maps for creature pathfinding. This step takes several hours.",
        "exe": "mmaps_generator.exe",
        "args": [],
        "output_dirs": ["mmaps"],
    },
]


class ClientLinkCard(ctk.CTkFrame):
    def __init__(self, master, link: dict, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8, **kwargs)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(inner, text=link["type"].upper(),
                     font=ctk.CTkFont("Segoe UI", 8, "bold"),
                     text_color=COLOR_ACCENT,
                     fg_color=COLOR_BG_SECONDARY,
                     corner_radius=4, padx=6, pady=2).pack(anchor="w")

        ctk.CTkLabel(inner, text=link["label"],
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(inner, text=link["description"],
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COLOR_TEXT_SECONDARY, anchor="w",
                     wraplength=280).pack(anchor="w")

        meta = ctk.CTkFrame(inner, fg_color="transparent")
        meta.pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(meta, text=f"Size: {link['size']}",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=COLOR_TEXT_MUTED).pack(side="left")

        ctk.CTkButton(meta, text="Open", width=80, height=26,
                      fg_color=COLOR_ACCENT, hover_color="#58a6ff",
                      font=ctk.CTkFont("Segoe UI", 10),
                      command=lambda u=link["url"]: webbrowser.open(u)).pack(side="right")


class ClientView(BaseView):

    def build_ui(self):
        self._header(self, "Client Setup",
                     "Download links, connection info, and game data extraction")

        self._tabs = ctk.CTkTabview(
            self, fg_color=COLOR_BG_CARD, corner_radius=8,
            segmented_button_fg_color=COLOR_BG_SECONDARY,
            segmented_button_selected_color=COLOR_ACCENT
        )
        self._tabs.pack(fill="both", expand=True, padx=24, pady=(8, 16))

        self._tabs.add("Client Downloads")
        self._tabs.add("Connection Info")
        self._tabs.add("Data Extraction")

        self._build_downloads_tab()
        self._build_connection_tab()
        self._build_extraction_tab()

    # ── Downloads Tab ─────────────────────────────────────────────────

    def _build_downloads_tab(self):
        tab = self._tabs.tab("Client Downloads")

        sel_row = ctk.CTkFrame(tab, fg_color="transparent")
        sel_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(sel_row, text="Expansion:",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY).pack(side="left")

        self._exp_var = ctk.StringVar(value="wotlk")
        ctk.CTkOptionMenu(
            sel_row, variable=self._exp_var,
            values=["vanilla", "tbc", "wotlk", "cata", "mop", "wod", "dragonflight"],
            width=140, height=28,
            fg_color="#21262d", button_color=COLOR_ACCENT,
            command=self._on_expansion_change
        ).pack(side="left", padx=8)

        self._links_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self._links_scroll.pack(fill="both", expand=True)
        self._links_scroll.columnconfigure((0, 1), weight=1)

        self._render_links("wotlk")

    def _render_links(self, expansion: str):
        for w in self._links_scroll.winfo_children():
            w.destroy()
        links = CLIENT_LINKS.get(expansion, [])
        row_i = 0
        col_i = 0
        for link in links:
            card = ClientLinkCard(self._links_scroll, link)
            card.grid(row=row_i, column=col_i, sticky="nsew",
                      padx=(0 if col_i == 0 else 8, 0), pady=(0, 10))
            col_i += 1
            if col_i >= 2:
                col_i = 0
                row_i += 1

    def _on_expansion_change(self, value: str):
        self._render_links(value)

    # ── Connection Info Tab ───────────────────────────────────────────

    def _build_connection_tab(self):
        tab = self._tabs.tab("Connection Info")

        realm_frame = ctk.CTkFrame(tab, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        realm_frame.pack(fill="x", pady=(0, 8))

        rl_inner = ctk.CTkFrame(realm_frame, fg_color="transparent")
        rl_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(rl_inner, text="Realmlist entry (add to WTF/Config.wtf)",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

        self._realmlist_lbl = ctk.CTkLabel(
            rl_inner, text="SET realmlist 127.0.0.1",
            font=ctk.CTkFont("Consolas", 12),
            text_color=COLOR_ACCENT
        )
        self._realmlist_lbl.pack(anchor="w", pady=(4, 0))

        ctk.CTkButton(
            rl_inner, text="Copy", width=80, height=28,
            fg_color=COLOR_BG_CARD, hover_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 10),
            command=self._copy_realmlist
        ).pack(anchor="w", pady=4)

        howto_frame = ctk.CTkFrame(tab, fg_color=COLOR_BG_CARD, corner_radius=8)
        howto_frame.pack(fill="x")

        ctk.CTkLabel(howto_frame, text="How to Connect",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=14, pady=(10, 0))

        for step in [
            "1. Download the correct game client (Client Downloads tab)",
            "2. Navigate to World of Warcraft/Data/enUS/realmlist.wtf (or WTF/Config.wtf)",
            "3. Replace the SET realmlist line with your server IP address",
            "4. Launch WoW.exe and log in with a registered account",
            "5. Use .account create <user> <pass> in the worldserver console to create accounts",
        ]:
            ctk.CTkLabel(howto_frame, text=step,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(
                anchor="w", padx=14, pady=1)
        ctk.CTkFrame(howto_frame, fg_color="transparent", height=8).pack()

    # ── Data Extraction Tab ───────────────────────────────────────────

    def _build_extraction_tab(self):
        tab = self._tabs.tab("Data Extraction")
        self._extract_vars: dict[str, ctk.BooleanVar] = {}

        info = ctk.CTkFrame(tab, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        info.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            info,
            text=(
                "Extract game data from your WoW client. The server requires these files to run.\n"
                "Set your WoW client path and install directory, then run each step in order."
            ),
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left", anchor="w", wraplength=600
        ).pack(padx=14, pady=8, anchor="w")

        # Path pickers
        paths_frame = ctk.CTkFrame(tab, fg_color=COLOR_BG_CARD, corner_radius=8)
        paths_frame.pack(fill="x", pady=(0, 8))

        for (label, attr, hint) in [
            ("WoW Client Dir", "_client_dir_entry", r"C:\World of Warcraft"),
            ("Install Dir",    "_install_dir_entry", r"C:\WoWServer\bin"),
        ]:
            row = ctk.CTkFrame(paths_frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(row, text=label, width=100,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(
                row, width=320, height=28, placeholder_text=hint,
                fg_color="#0d1117", border_color=COLOR_BORDER,
                text_color=COLOR_TEXT_PRIMARY, font=ctk.CTkFont("Consolas", 10)
            )
            entry.pack(side="left", padx=8)
            setattr(self, attr, entry)

            ctk.CTkButton(
                row, text="Browse", width=70, height=28,
                fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BORDER,
                font=ctk.CTkFont("Segoe UI", 10),
                command=lambda a=attr: self._browse_dir(a)
            ).pack(side="left")

        # Extractor step list
        steps_frame = ctk.CTkFrame(tab, fg_color=COLOR_BG_CARD, corner_radius=8)
        steps_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(steps_frame, text="Extraction Steps (run in order)",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=14, pady=(8, 4))

        self._step_status_labels: dict[str, ctk.CTkLabel] = {}

        for ext in EXTRACTORS:
            row = ctk.CTkFrame(steps_frame, fg_color=COLOR_BG_SECONDARY, corner_radius=6)
            row.pack(fill="x", padx=14, pady=3)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=6)

            var = ctk.BooleanVar(value=(ext["id"] != "mmaps"))
            self._extract_vars[ext["id"]] = var
            ctk.CTkCheckBox(inner, variable=var, text="",
                            width=20, checkbox_width=16, checkbox_height=16).pack(side="left")

            col = ctk.CTkFrame(inner, fg_color="transparent")
            col.pack(side="left", padx=8, fill="y")
            ctk.CTkLabel(col, text=ext["label"],
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(anchor="w")
            ctk.CTkLabel(col, text=ext["description"],
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=COLOR_TEXT_MUTED, anchor="w").pack(anchor="w")

            status = ctk.CTkLabel(inner, text="○", font=ctk.CTkFont("Segoe UI", 14),
                                  text_color=COLOR_TEXT_MUTED, width=24)
            status.pack(side="right")
            self._step_status_labels[ext["id"]] = status

        ctk.CTkFrame(steps_frame, fg_color="transparent", height=6).pack()

        # Action buttons
        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))

        self._extract_btn = ctk.CTkButton(
            btn_row, text="▶  Run Selected Extractors", height=36, width=200,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._run_extraction
        )
        self._extract_btn.pack(side="left")

        self._extract_cancel_btn = ctk.CTkButton(
            btn_row, text="■  Stop", height=36, width=80,
            fg_color=COLOR_ERROR, hover_color="#ff6b6b",
            font=ctk.CTkFont("Segoe UI", 12),
            state="disabled",
            command=self._cancel_extraction
        )
        self._extract_cancel_btn.pack(side="left", padx=8)

        self._extract_log = LogConsole(tab, height=120)
        self._extract_log.pack(fill="both", expand=True)
        self._extract_cancelled = False

    def _browse_dir(self, attr: str):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Select Directory")
        if path:
            entry = getattr(self, attr)
            entry.delete(0, "end")
            entry.insert(0, path)

    def _run_extraction(self):
        client_dir = self._client_dir_entry.get().strip()
        install_dir = self._install_dir_entry.get().strip()

        if not client_dir or not Path(client_dir).exists():
            self._extract_log.append("[ERROR] WoW client directory not found or not set", "error")
            return
        if not install_dir or not Path(install_dir).exists():
            self._extract_log.append("[ERROR] Install directory not found — build the server first", "error")
            return

        selected = [e for e in EXTRACTORS if self._extract_vars[e["id"]].get()]
        if not selected:
            self._extract_log.append("[WARN] No extraction steps selected", "warning")
            return

        self._extract_btn.configure(state="disabled", text="Extracting...")
        self._extract_cancel_btn.configure(state="normal")
        self._extract_cancelled = False
        self._extract_log.clear()
        for eid in self._step_status_labels:
            self._step_status_labels[eid].configure(text="○", text_color=COLOR_TEXT_MUTED)

        get_workers().submit("extraction", self._do_extraction,
                             client_dir, install_dir, selected)

    def _do_extraction(self, client_dir: str, install_dir: str, steps: list[dict]):
        install_path = Path(install_dir)
        client_path = Path(client_dir)

        for step in steps:
            if self._extract_cancelled:
                break

            exe_path = install_path / step["exe"]
            if not exe_path.exists():
                msg = f"[ERROR] {step['exe']} not found in {install_dir}. Build the server with Tools enabled."
                self.after(0, lambda m=msg: self._extract_log.append(m, "error"))
                self.after(0, lambda eid=step["id"]: self._step_status_labels[eid].configure(
                    text="✗", text_color=COLOR_ERROR))
                continue

            self.after(0, lambda eid=step["id"]: self._step_status_labels[eid].configure(
                text="⟳", text_color=COLOR_WARNING))
            self.after(0, lambda lbl=step["label"]: self._extract_log.append(
                f"[INFO] Running {lbl}...", "info"))

            # Build full arg list
            cmd = [str(exe_path)] + step["args"]
            try:
                proc = subprocess.Popen(
                    cmd, cwd=str(client_path),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, encoding="utf-8", errors="replace"
                )
                for line in proc.stdout:
                    if self._extract_cancelled:
                        proc.terminate()
                        break
                    line = line.rstrip()
                    if line:
                        self.after(0, lambda l=line: self._extract_log.append(f"  {l}"))
                proc.wait()
                ok = proc.returncode == 0 and not self._extract_cancelled
            except Exception as e:
                ok = False
                self.after(0, lambda err=str(e): self._extract_log.append(
                    f"[ERROR] {err}", "error"))

            icon, color = ("✓", COLOR_SUCCESS) if ok else ("✗", COLOR_ERROR)
            self.after(0, lambda eid=step["id"], i=icon, c=color:
                       self._step_status_labels[eid].configure(text=i, text_color=c))
            if ok:
                self.after(0, lambda lbl=step["label"]: self._extract_log.append(
                    f"[OK] {lbl} complete", "success"))

        self.after(0, self._extraction_done)

    def _extraction_done(self):
        self._extract_btn.configure(state="normal", text="▶  Run Selected Extractors")
        self._extract_cancel_btn.configure(state="disabled")
        if self._extract_cancelled:
            self._extract_log.append("[CANCELLED] Extraction cancelled", "warning")
        else:
            self._extract_log.append("[DONE] Extraction finished. Copy output folders to your server directory.", "success")

    def _cancel_extraction(self):
        self._extract_cancelled = True
        self._extract_cancel_btn.configure(state="disabled")

    # ── Shared ────────────────────────────────────────────────────────

    def refresh(self):
        profile = self.state.active_profile
        if not profile:
            return
        ip = profile.network_config.external_ip or "127.0.0.1"
        if hasattr(self, "_realmlist_lbl"):
            self._realmlist_lbl.configure(text=f"SET realmlist {ip}")

        sdef = self.app.get_server_def(profile.server_id) or {}
        exp = sdef.get("expansion", "wotlk")
        if hasattr(self, "_exp_var"):
            self._exp_var.set(exp)
            self._render_links(exp)

        # Pre-fill install dir from profile
        if hasattr(self, "_install_dir_entry") and profile.install_dir:
            self._install_dir_entry.delete(0, "end")
            self._install_dir_entry.insert(0, profile.install_dir)

    def _copy_realmlist(self):
        text = self._realmlist_lbl.cget("text")
        self.clipboard_clear()
        self.clipboard_append(text)
