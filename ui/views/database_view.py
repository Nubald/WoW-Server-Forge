"""Database setup view — connect, create DBs, import SQL."""
from __future__ import annotations

from pathlib import Path
import customtkinter as ctk
from ui.views.base_view import BaseView
from ui.widgets.log_console import LogConsole
from core.database_manager import DatabaseManager
from services.worker_service import get_workers
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING
)


class DatabaseView(BaseView):

    def build_ui(self):
        self._header(self, "Database Setup",
                     "Connect to MySQL, create databases, and import server data")
        self._db_mgr = DatabaseManager()
        self._connected = False

        # Tabview
        self._tabs = ctk.CTkTabview(self, fg_color=COLOR_BG_CARD, corner_radius=8,
                                    segmented_button_fg_color=COLOR_BG_SECONDARY,
                                    segmented_button_selected_color=COLOR_ACCENT)
        self._tabs.pack(fill="both", expand=True, padx=24, pady=(8, 16))

        self._tabs.add("Connection")
        self._tabs.add("Databases")
        self._tabs.add("TDB Download")

        self._build_connection_tab()
        self._build_databases_tab()
        self._build_tdb_tab()

    def _build_connection_tab(self):
        tab = self._tabs.tab("Connection")

        form = ctk.CTkFrame(tab, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        form.pack(fill="x", padx=0, pady=8)

        fields = [
            ("Host",     "host_entry",     "127.0.0.1"),
            ("Port",     "port_entry",     "3306"),
            ("Username", "user_entry",     "trinity"),
            ("Password", "pass_entry",     "trinity"),
        ]
        for label, attr, placeholder in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(row, text=label, width=80,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(
                row, width=260, height=30, placeholder_text=placeholder,
                fg_color="#0d1117", border_color=COLOR_BORDER,
                text_color=COLOR_TEXT_PRIMARY,
                show="*" if attr == "pass_entry" else ""
            )
            entry.pack(side="left", padx=8)
            setattr(self, f"_{attr}", entry)

        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=8)
        self._conn_btn = ctk.CTkButton(
            btn_row, text="Test Connection", width=140, height=32,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._test_connection
        )
        self._conn_btn.pack(side="left")
        self._conn_status = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._conn_status.pack(side="left", padx=12)

        # Create user section
        user_frame = ctk.CTkFrame(tab, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        user_frame.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(user_frame, text="Create MySQL User (optional — uses root first)",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COLOR_TEXT_MUTED).pack(padx=14, pady=(8, 0), anchor="w")
        ctk.CTkButton(
            user_frame, text="Create forge user from profile settings",
            height=28, fg_color=COLOR_BG_CARD, hover_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 11), text_color=COLOR_TEXT_SECONDARY,
            command=self._create_user
        ).pack(padx=14, pady=8, anchor="w")

    def _build_databases_tab(self):
        tab = self._tabs.tab("Databases")
        self._db_rows: dict[str, dict] = {}

        all_btn = ctk.CTkButton(
            tab, text="⟳  Setup All Databases", height=34, width=200,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._setup_all
        )
        all_btn.pack(anchor="w", pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        db_names = [
            ("auth",       "Auth Database",       "Authentication (accounts, realms)"),
            ("characters", "Characters Database", "Player characters and inventories"),
            ("world",      "World Database",      "World data, creatures, quests"),
        ]
        for db_key, db_label, db_desc in db_names:
            row = ctk.CTkFrame(scroll, fg_color=COLOR_BG_CARD, corner_radius=8)
            row.pack(fill="x", pady=4)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)

            col = ctk.CTkFrame(inner, fg_color="transparent")
            col.pack(side="left", fill="y")
            ctk.CTkLabel(col, text=db_label,
                         font=ctk.CTkFont("Segoe UI", 12, "bold"),
                         text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(anchor="w")
            ctk.CTkLabel(col, text=db_desc,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=COLOR_TEXT_MUTED, anchor="w").pack(anchor="w")

            status_lbl = ctk.CTkLabel(inner, text="◌",
                                      font=ctk.CTkFont("Segoe UI", 16),
                                      text_color=COLOR_TEXT_MUTED)
            status_lbl.pack(side="right")

            prog = ctk.CTkProgressBar(inner, width=120, height=6,
                                       fg_color=COLOR_BORDER, progress_color=COLOR_ACCENT)
            prog.set(0)
            prog.pack(side="right", padx=8)

            upd_btn = ctk.CTkButton(
                inner, text="Updates", width=70, height=28,
                fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BORDER,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=COLOR_TEXT_SECONDARY,
                command=lambda k=db_key: self._apply_updates(k)
            )
            upd_btn.pack(side="right", padx=(0, 4))

            imp_btn = ctk.CTkButton(
                inner, text="Import", width=70, height=28,
                fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BORDER,
                font=ctk.CTkFont("Segoe UI", 11),
                command=lambda k=db_key: self._import_db(k)
            )
            imp_btn.pack(side="right", padx=(0, 8))

            self._db_rows[db_key] = {"status": status_lbl, "progress": prog,
                                     "btn": imp_btn, "upd_btn": upd_btn}

        self._db_log = LogConsole(tab, height=150)
        self._db_log.pack(fill="x", pady=(8, 0))

    def _build_tdb_tab(self):
        tab = self._tabs.tab("TDB Download")
        ctk.CTkLabel(tab, text="TrinityCore World Database (TDB)",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(tab,
                     text="The world database contains all creatures, quests, items, and scripts.\n"
                          "Download the latest TDB release from GitHub to populate your world_db.",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY, justify="left").pack(anchor="w", pady=4)

        info = ctk.CTkFrame(tab, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        info.pack(fill="x", pady=8)
        self._tdb_lbl = ctk.CTkLabel(info, text="Latest TDB: checking...",
                                     font=ctk.CTkFont("Consolas", 11),
                                     text_color=COLOR_TEXT_SECONDARY)
        self._tdb_lbl.pack(padx=14, pady=8, anchor="w")

        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.pack(fill="x", pady=4)
        ctk.CTkButton(btn_row, text="⬇  Open TDB Releases Page", height=34,
                      fg_color=COLOR_ACCENT, hover_color="#58a6ff",
                      font=ctk.CTkFont("Segoe UI", 12),
                      command=self._open_tdb).pack(side="left")

        ctk.CTkButton(btn_row, text="⟳  Check Latest Version", height=34, width=180,
                      fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BG_CARD,
                      border_width=1, border_color=COLOR_BORDER,
                      font=ctk.CTkFont("Segoe UI", 12),
                      command=self._check_tdb).pack(side="left", padx=8)

    def _test_connection(self):
        host = self._host_entry.get() or "127.0.0.1"
        port = int(self._port_entry.get() or 3306)
        user = self._user_entry.get() or "trinity"
        password = self._pass_entry.get() or "trinity"
        self._conn_btn.configure(state="disabled", text="Connecting...")
        get_workers().submit("db_test", self._do_test, host, port, user, password)

    def _do_test(self, host, port, user, password):
        ok, msg = self._db_mgr.test_connection(host, port, user, password)
        if ok:
            self._db_mgr.connect(host, port, user, password)
            self._connected = True
            # Save to profile
            if self.state.active_profile:
                p = self.state.active_profile
                p.db_config.host = host
                p.db_config.port = port
                p.db_config.user = user
                p.db_config.password = password
                p.save(self.app.profiles_dir)
        self.after(0, lambda: self._conn_btn.configure(state="normal", text="Test Connection"))
        self.after(0, lambda: self._conn_status.configure(
            text=("✓ " if ok else "✗ ") + msg,
            text_color=COLOR_SUCCESS if ok else COLOR_ERROR
        ))

    def _create_user(self):
        profile = self.state.active_profile
        if not profile or not self._connected:
            return
        self._db_mgr.create_user(profile.db_config.user, profile.db_config.password)

    def _setup_all(self):
        if not self._connected:
            self._db_log.append("[ERROR] Connect to MySQL first", "error")
            return
        profile = self.state.active_profile
        if not profile:
            return
        for db_key in ["auth", "characters", "world"]:
            db_name = getattr(profile.db_config, f"{db_key}_db", db_key)
            self._db_mgr.create_database(db_name)
        self._db_log.append("[OK] Databases created", "success")
        self._import_db("auth")
        # Schedule realm registration after auth import kicks off
        self.after(500, self._register_realm)

    def _register_realm(self):
        profile = self.state.active_profile
        if not profile:
            return
        auth_db = getattr(profile.db_config, "auth_db", "auth")
        realm_name = getattr(profile, "name", "My WoW Server")
        ip = profile.network_config.external_ip or "127.0.0.1"
        world_port = profile.network_config.world_port or 8085
        # Expansion: derive from server def
        sdef = self.app.get_server_def(profile.server_id) or {}
        exp_map = {"vanilla": 0, "tbc": 1, "wotlk": 2}
        expansion = exp_map.get(sdef.get("expansion", "wotlk"), 2)
        ok, msg = self._db_mgr.register_realm(realm_name, ip, auth_db, world_port, expansion)
        level = "success" if ok else "error"
        self._db_log.append(f"[Realm] {msg}", level)

    def _import_db(self, db_key: str):
        profile = self.state.active_profile
        if not profile:
            return
        source_dir = self.app.get_source_dir()
        if not source_dir:
            self._db_log.append("[ERROR] Source directory not found", "error")
            return
        db_name = getattr(profile.db_config, f"{db_key}_db", db_key)
        sdef = self.app.get_server_def(profile.server_id) or {}
        db_entry = next((d for d in sdef.get("databases", []) if d["key"] == db_key), {})
        sql_dir_rel = db_entry.get("sql_dir", f"sql/base/{db_key}")
        sql_dir = source_dir / sql_dir_rel
        if not sql_dir.exists():
            self._db_log.append(f"[WARN] SQL directory not found: {sql_dir}", "warning")
            return
        get_workers().submit(f"import_{db_key}", self._do_import, db_key, db_name, sql_dir)

    def _apply_updates(self, db_key: str):
        if not self._connected:
            self._db_log.append("[ERROR] Connect to MySQL first", "error")
            return
        profile = self.state.active_profile
        if not profile:
            return
        source_dir = self.app.get_source_dir()
        if not source_dir:
            self._db_log.append("[ERROR] Source directory not found", "error")
            return
        db_name = getattr(profile.db_config, f"{db_key}_db", db_key)
        get_workers().submit(f"updates_{db_key}", self._do_updates, db_key, db_name, source_dir)

    def _do_updates(self, db_key: str, db_name: str, source_dir: Path):
        row = self._db_rows.get(db_key, {})
        if row:
            self.after(0, lambda: row["status"].configure(text="⟳", text_color=COLOR_WARNING))
        for line in self._db_mgr.import_updates(db_name, source_dir, db_key):
            self.after(0, lambda l=line: self._db_log.append(l))
        if row:
            self.after(0, lambda: row["status"].configure(text="✓", text_color=COLOR_SUCCESS))

    def _do_import(self, db_key: str, db_name: str, sql_dir: Path):
        row = self._db_rows.get(db_key, {})
        if row:
            self.after(0, lambda: row["status"].configure(text="⟳", text_color=COLOR_WARNING))
        for line in self._db_mgr.import_directory(db_name, sql_dir):
            self.after(0, lambda l=line: self._db_log.append(l))
        if row:
            self.after(0, lambda: row["status"].configure(text="✓", text_color=COLOR_SUCCESS))
            self.after(0, lambda: row["progress"].set(1))

    def _open_tdb(self):
        import webbrowser
        webbrowser.open("https://github.com/TrinityCore/TrinityCore/releases")

    def _check_tdb(self):
        import requests, threading
        def fetch():
            try:
                r = requests.get(
                    "https://api.github.com/repos/TrinityCore/TrinityCore/releases/latest",
                    timeout=8
                )
                data = r.json()
                tag = data.get("tag_name", "Unknown")
                self.after(0, lambda: self._tdb_lbl.configure(
                    text=f"Latest TDB release: {tag}", text_color=COLOR_SUCCESS
                ))
            except Exception as e:
                self.after(0, lambda: self._tdb_lbl.configure(
                    text=f"Could not fetch: {e}", text_color=COLOR_WARNING
                ))
        threading.Thread(target=fetch, daemon=True).start()

    def refresh(self):
        profile = self.state.active_profile
        if not profile:
            return
        db = profile.db_config
        if hasattr(self, "_host_entry"):
            self._host_entry.delete(0, "end")
            self._host_entry.insert(0, db.host)
            self._port_entry.delete(0, "end")
            self._port_entry.insert(0, str(db.port))
            self._user_entry.delete(0, "end")
            self._user_entry.insert(0, db.user)
