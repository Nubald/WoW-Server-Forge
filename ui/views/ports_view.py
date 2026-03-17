"""Ports and network configuration view."""
from __future__ import annotations

import socket
import customtkinter as ctk
from ui.views.base_view import BaseView
from app.constants import (
    DEFAULT_PORTS, COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING
)


class PortRow(ctk.CTkFrame):
    def __init__(self, master, label: str, default: int, profile_attr: str, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8, height=52, **kwargs)
        self.pack_propagate(False)
        self._attr = profile_attr

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14)

        ctk.CTkLabel(inner, text=label, width=180,
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(side="left")

        self._entry = ctk.CTkEntry(
            inner, width=90, height=28, placeholder_text=str(default),
            fg_color="#0d1117", border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont("Consolas", 11)
        )
        self._entry.insert(0, str(default))
        self._entry.pack(side="left", padx=8)

        self._status_lbl = ctk.CTkLabel(inner, text="—",
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        text_color=COLOR_TEXT_MUTED, width=80)
        self._status_lbl.pack(side="left")

        ctk.CTkButton(inner, text="Check", width=70, height=26,
                      fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BORDER,
                      font=ctk.CTkFont("Segoe UI", 10),
                      command=self._check_port).pack(side="right")

    def get_port(self) -> int:
        try:
            return int(self._entry.get())
        except ValueError:
            return 0

    def set_value(self, value: int):
        self._entry.delete(0, "end")
        self._entry.insert(0, str(value))

    def _check_port(self):
        port = self.get_port()
        available = self._is_available(port)
        if available:
            self._status_lbl.configure(text="✓ Available", text_color=COLOR_SUCCESS)
        else:
            self._status_lbl.configure(text="✗ In use", text_color=COLOR_ERROR)

    def _is_available(self, port: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            result = s.connect_ex(("127.0.0.1", port))
            s.close()
            return result != 0
        except Exception:
            return True


class PortsView(BaseView):

    def build_ui(self):
        self._header(self, "Ports & Network",
                     "Configure server ports, realm name, and firewall rules")

        # Realm info section
        realm_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        realm_frame.pack(fill="x", padx=24, pady=(8, 0))

        row = ctk.CTkFrame(realm_frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(row, text="Realm Name:", width=140,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(side="left")
        self._realm_entry = ctk.CTkEntry(row, width=260, height=30,
                                          placeholder_text="My WoW Server",
                                          fg_color="#0d1117", border_color=COLOR_BORDER,
                                          text_color=COLOR_TEXT_PRIMARY)
        self._realm_entry.pack(side="left", padx=8)

        row2 = ctk.CTkFrame(realm_frame, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(row2, text="External IP:", width=140,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(side="left")
        self._ip_entry = ctk.CTkEntry(row2, width=160, height=30,
                                       placeholder_text="127.0.0.1",
                                       fg_color="#0d1117", border_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT_PRIMARY)
        self._ip_entry.pack(side="left", padx=8)

        self._detect_ip_btn = ctk.CTkButton(
            row2, text="Detect", width=70, height=28,
            fg_color=COLOR_BG_CARD, hover_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 10),
            command=self._detect_ip
        )
        self._detect_ip_btn.pack(side="left")

        # Port rows
        ctk.CTkLabel(self, text="Port Configuration",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", padx=24, pady=(12, 4))

        port_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=240)
        port_scroll.pack(fill="x", padx=24)

        port_defs = [
            ("Auth Server Port (login)",    DEFAULT_PORTS["auth_port"],  "auth_port"),
            ("World Server Port (game)",    DEFAULT_PORTS["world_port"], "world_port"),
            ("MySQL Port (database)",       DEFAULT_PORTS["mysql_port"], "mysql_port"),
            ("SOAP Port (remote admin)",    DEFAULT_PORTS["soap_port"],  "soap_port"),
            ("Remote Access Port (RA)",     DEFAULT_PORTS["ra_port"],    "ra_port"),
        ]
        self._port_rows: dict[str, PortRow] = {}
        for label, default, attr in port_defs:
            pr = PortRow(port_scroll, label, default, attr)
            pr.pack(fill="x", pady=3)
            self._port_rows[attr] = pr

        # Action buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=12)

        ctk.CTkButton(
            btn_row, text="✓  Check All Ports", height=36, width=160,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._check_all
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="🔒  Add Firewall Rules", height=36, width=170,
            fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BG_CARD,
            border_width=1, border_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._add_firewall_rules
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="💾  Save", height=36, width=100,
            fg_color=COLOR_SUCCESS, hover_color="#45c55a",
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._save
        ).pack(side="right")

        self._msg_lbl = ctk.CTkLabel(self, text="",
                                      font=ctk.CTkFont("Segoe UI", 11),
                                      text_color=COLOR_TEXT_SECONDARY)
        self._msg_lbl.pack(anchor="w", padx=24)

    def refresh(self):
        profile = self.state.active_profile
        if not profile:
            return
        net = profile.network_config
        if hasattr(self, "_realm_entry"):
            self._realm_entry.delete(0, "end")
            self._realm_entry.insert(0, net.realm_name)
            self._ip_entry.delete(0, "end")
            self._ip_entry.insert(0, net.external_ip)
        for attr, row in self._port_rows.items():
            val = getattr(net, attr, None)
            if val:
                row.set_value(val)

    def _check_all(self):
        for row in self._port_rows.values():
            row._check_port()

    def _save(self):
        profile = self.state.active_profile
        if not profile:
            return
        net = profile.network_config
        net.realm_name = self._realm_entry.get() or net.realm_name
        net.external_ip = self._ip_entry.get() or net.external_ip
        for attr, row in self._port_rows.items():
            port = row.get_port()
            if port > 0:
                setattr(net, attr, port)
        profile.save(self.app.profiles_dir)
        self._msg_lbl.configure(text="✓ Saved", text_color=COLOR_SUCCESS)

    def _detect_ip(self):
        import urllib.request
        try:
            ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
            self._ip_entry.delete(0, "end")
            self._ip_entry.insert(0, ip)
        except Exception:
            self._msg_lbl.configure(text="Could not detect IP", text_color=COLOR_WARNING)

    def _add_firewall_rules(self):
        import subprocess
        ports = [(attr, row.get_port()) for attr, row in self._port_rows.items()]
        for attr, port in ports:
            if port <= 0:
                continue
            subprocess.run([
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name=WoWForge_{attr}_{port}",
                "dir=in", "action=allow",
                "protocol=TCP", f"localport={port}"
            ], capture_output=True)
        self._msg_lbl.configure(text="✓ Firewall rules added", text_color=COLOR_SUCCESS)
