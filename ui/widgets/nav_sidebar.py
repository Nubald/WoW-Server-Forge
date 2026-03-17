"""Left navigation sidebar widget."""
from __future__ import annotations

from typing import Callable
import customtkinter as ctk
from app.constants import (
    NAV_SECTIONS, COLOR_SIDEBAR_BG, COLOR_SIDEBAR_SELECT,
    COLOR_ACCENT, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED, COLOR_BORDER, COLOR_BG_SECONDARY
)


class NavSidebar(ctk.CTkFrame):
    """Fixed-width sidebar with grouped navigation items."""

    def __init__(self, master, on_navigate: Callable[[str], None],
                 get_profiles: Callable[[], list[str]] | None = None,
                 on_profile_switch: Callable[[str], None] | None = None,
                 **kwargs):
        super().__init__(
            master,
            width=220, fg_color=COLOR_SIDEBAR_BG,
            corner_radius=0,
            **kwargs
        )
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._get_profiles = get_profiles
        self._on_profile_switch = on_profile_switch
        self._active_id = "dashboard"
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._profile_menu: ctk.CTkOptionMenu | None = None
        self._profile_var: ctk.StringVar | None = None
        self._build_ui()

    def _build_ui(self):
        # Logo area
        logo_frame = ctk.CTkFrame(self, fg_color="transparent", height=70)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)

        ctk.CTkLabel(
            logo_frame,
            text="⚔  SERVER FORGE",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=COLOR_ACCENT
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Divider
        ctk.CTkFrame(self, fg_color=COLOR_BORDER, height=1).pack(fill="x")

        # Scrollable area for nav items
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLOR_SIDEBAR_BG,
            scrollbar_button_hover_color=COLOR_BORDER
        )
        scroll.pack(fill="both", expand=True, pady=(4, 0))

        for section in NAV_SECTIONS:
            # Section label
            ctk.CTkLabel(
                scroll,
                text=section["label"],
                font=ctk.CTkFont("Segoe UI", 9, "bold"),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            ).pack(fill="x", padx=16, pady=(12, 2))

            for item in section["items"]:
                btn = ctk.CTkButton(
                    scroll,
                    text=f"  {item['icon']}  {item['label']}",
                    anchor="w",
                    height=36,
                    corner_radius=6,
                    fg_color="transparent",
                    hover_color=COLOR_SIDEBAR_SELECT,
                    text_color=COLOR_TEXT_SECONDARY,
                    font=ctk.CTkFont("Segoe UI", 12),
                    command=lambda iid=item["id"]: self._on_click(iid)
                )
                btn.pack(fill="x", padx=8, pady=1)
                self._buttons[item["id"]] = btn

        # Bottom section — profile switcher + version
        ctk.CTkFrame(self, fg_color=COLOR_BORDER, height=1).pack(fill="x", pady=(4, 0))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            bottom,
            text="PROFILE",
            font=ctk.CTkFont("Segoe UI", 8, "bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill="x")

        self._profile_var = ctk.StringVar(value="No profile")
        self._profile_menu = ctk.CTkOptionMenu(
            bottom,
            variable=self._profile_var,
            values=["No profile"],
            width=180, height=28,
            fg_color=COLOR_BG_SECONDARY,
            button_color=COLOR_SIDEBAR_SELECT,
            button_hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont("Segoe UI", 10),
            command=self._on_profile_selected
        )
        self._profile_menu.pack(fill="x", pady=(2, 4))

        ctk.CTkLabel(
            bottom,
            text="One Click Server Forge v1.0",
            font=ctk.CTkFont("Segoe UI", 8),
            text_color=COLOR_TEXT_MUTED
        ).pack(fill="x")

        self._set_active("dashboard")

    def _on_click(self, item_id: str) -> None:
        self._set_active(item_id)
        self._on_navigate(item_id)

    def _on_profile_selected(self, name: str) -> None:
        if self._on_profile_switch and name != "No profile":
            self._on_profile_switch(name)

    def _set_active(self, item_id: str) -> None:
        # Deactivate old
        if self._active_id in self._buttons:
            self._buttons[self._active_id].configure(
                fg_color="transparent",
                text_color=COLOR_TEXT_SECONDARY
            )
        # Activate new
        self._active_id = item_id
        if item_id in self._buttons:
            self._buttons[item_id].configure(
                fg_color=COLOR_SIDEBAR_SELECT,
                text_color=COLOR_TEXT_PRIMARY
            )

    def set_active(self, item_id: str) -> None:
        self._set_active(item_id)

    def refresh_profiles(self, profile_names: list[str], active_name: str) -> None:
        """Update the profile dropdown with current profiles."""
        if not self._profile_menu or not self._profile_var:
            return
        values = profile_names if profile_names else ["No profile"]
        self._profile_menu.configure(values=values)
        display = active_name if active_name in values else (values[0] if values else "No profile")
        self._profile_var.set(display)
