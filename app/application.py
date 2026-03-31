"""Main application class — owns the CTk root, navigation, and view lifecycle."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from app.constants import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT,
    SIDEBAR_WIDTH, SERVERS_DIR, PROFILES_DIR, LOGS_DIR, COLOR_BG_DARK,
    COLOR_TEXT_PRIMARY, COLOR_ACCENT
)
from app.state import AppState, get_state
from services.event_bus import get_bus, EventBus
from services.log_service import get_log
from services.worker_service import get_workers
from ui.widgets.nav_sidebar import NavSidebar
from ui.widgets.status_bar import StatusBar


class ForgeApplication:
    """Root application controller."""

    def __init__(self):
        self.state = get_state()
        self.bus: EventBus = get_bus()
        self.profiles_dir = PROFILES_DIR

        # Configure CustomTkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Create root window (the ONE tkinter root — never create a second one)
        self.root = ctk.CTk()
        self.root.title(f"{APP_NAME}  v{APP_VERSION}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.configure(fg_color=COLOR_BG_DARK)

        # Try to set icon
        icon_path = Path(__file__).parent.parent / "forge.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Connect EventBus to root for thread-safe dispatch
        self.bus.set_root(self.root)

        # Permanent app-level listeners (never unsubscribed)
        self.bus.subscribe("process.status_changed", self._on_process_status)

        # Load views lazily (first visit builds UI)
        self._views: dict[str, any] = {}
        self._current_view = None

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Hide main window while splash runs; _finish_init reveals it
        self.root.withdraw()
        self._show_splash()

    def _show_splash(self):
        """Show a splash CTkToplevel on the real root, then call _finish_init."""
        from app.constants import COLOR_TEXT_SECONDARY
        splash = ctk.CTkToplevel(self.root)
        splash.overrideredirect(True)
        splash.configure(fg_color=COLOR_BG_DARK)
        splash.attributes("-topmost", True)
        splash.lift()

        w, h = 420, 200
        sw = splash.winfo_screenwidth()
        sh = splash.winfo_screenheight()
        splash.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        ctk.CTkLabel(splash, text="⚔", font=ctk.CTkFont("Segoe UI", 48),
                     text_color=COLOR_ACCENT).pack(pady=(28, 0))
        ctk.CTkLabel(splash, text="One Click Server Forge",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=COLOR_TEXT_PRIMARY).pack()
        ctk.CTkLabel(splash, text=f"v{APP_VERSION}  —  Loading...",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY).pack()

        self._splash = splash
        # Give the splash 1.5 s then switch to the real window
        self.root.after(1500, self._finish_init)

    def _finish_init(self):
        """Destroy splash and reveal the fully-built main window."""
        if self._splash and self._splash.winfo_exists():
            self._splash.destroy()
        self._splash = None

        self._bootstrap()
        self._build_layout()
        self.show_view("dashboard")
        get_workers().submit("startup_prereq_check", self._startup_checks)

        self.root.deiconify()

        # Show first-run wizard if no profiles exist yet
        if not self.state.active_profile:
            self.root.after(600, self._show_first_run_wizard)

    def _bootstrap(self):
        """Initialize directories, logging, and load data."""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        log = get_log()
        log.init(LOGS_DIR)
        log.info(f"{APP_NAME} v{APP_VERSION} starting up")

        # Load all server definitions
        self._load_server_defs()

        # Load most recent profile (if any)
        from models.server_profile import ServerProfile
        profiles = ServerProfile.load_all(PROFILES_DIR)
        if profiles:
            self.state.active_profile = profiles[-1]
            log.info(f"Loaded profile: {profiles[-1].name}")

    def _load_server_defs(self):
        if SERVERS_DIR.exists():
            for f in SERVERS_DIR.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self.state.server_defs[data["id"]] = data
                except Exception as e:
                    get_log().warning(f"Failed to load server def {f.name}: {e}")

    def _build_layout(self):
        """Construct sidebar + content area + status bar."""
        # Main container
        self._main = ctk.CTkFrame(self.root, fg_color=COLOR_BG_DARK, corner_radius=0)
        self._main.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = NavSidebar(
            self._main,
            on_navigate=self.show_view,
            get_profiles=self._get_profile_names,
            on_profile_switch=self._switch_profile,
        )
        self.sidebar.pack(side="left", fill="y")

        # Content frame
        self._content = ctk.CTkFrame(self._main, fg_color=COLOR_BG_DARK, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        # Status bar (at root level, below main)
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side="bottom", fill="x")

        profile = self.state.active_profile
        if profile:
            self.status_bar.set_profile(profile.name)
        self._refresh_profile_switcher()

    def show_view(self, view_id: str) -> None:
        """Navigate to a view by ID."""
        from ui.views.dashboard_view     import DashboardView
        from ui.views.prerequisites_view import PrerequisitesView
        from ui.views.server_select_view import ServerSelectView
        from ui.views.source_view        import SourceView
        from ui.views.modules_view       import ModulesView
        from ui.views.build_view         import BuildView
        from ui.views.database_view      import DatabaseView
        from ui.views.config_view        import ConfigView
        from ui.views.ports_view         import PortsView
        from ui.views.control_view       import ControlView
        from ui.views.client_view        import ClientView

        VIEW_CLASSES = {
            "dashboard":    DashboardView,
            "prerequisites": PrerequisitesView,
            "server_select": ServerSelectView,
            "source":        SourceView,
            "modules":       ModulesView,
            "build":         BuildView,
            "database":      DatabaseView,
            "config":        ConfigView,
            "ports":         PortsView,
            "control":       ControlView,
            "client":        ClientView,
        }

        if view_id not in VIEW_CLASSES:
            return

        # Exit current view
        if self._current_view is not None:
            self._current_view.on_exit()
            self._current_view.pack_forget()

        # Create view if not cached
        if view_id not in self._views:
            cls = VIEW_CLASSES[view_id]
            view = cls(self._content, app=self)
            self._views[view_id] = view

        # Show new view
        view = self._views[view_id]
        view.pack(fill="both", expand=True)
        view.on_enter()
        self._current_view = view
        self.sidebar.set_active(view_id)
        self._refresh_profile_switcher()

    def get_server_def(self, server_id: str) -> Optional[dict]:
        return self.state.server_defs.get(server_id)

    def get_source_dir(self) -> Optional[Path]:
        profile = self.state.active_profile
        if not profile:
            return None
        if profile.source_dir:
            return Path(profile.source_dir)
        return Path(profile.workspace_dir) / "source"

    def _show_first_run_wizard(self) -> None:
        from ui.widgets.first_run_wizard import FirstRunWizard
        FirstRunWizard(self.root, on_navigate=self.show_view)

    def _get_profile_names(self) -> list[str]:
        from models.server_profile import ServerProfile
        profiles = ServerProfile.load_all(self.profiles_dir)
        return [p.name for p in profiles]

    def _switch_profile(self, name: str) -> None:
        from models.server_profile import ServerProfile
        profiles = ServerProfile.load_all(self.profiles_dir)
        target = next((p for p in profiles if p.name == name), None)
        if not target:
            return
        self.state.active_profile = target
        get_log().info(f"Switched to profile: {name}")
        self.status_bar.set_profile(name)
        # Refresh the active view so it picks up the new profile
        if self._current_view is not None:
            self._current_view.refresh()

    def _refresh_profile_switcher(self) -> None:
        if not hasattr(self, "sidebar"):
            return
        from models.server_profile import ServerProfile
        profiles = ServerProfile.load_all(self.profiles_dir)
        names = [p.name for p in profiles]
        active = self.state.active_profile.name if self.state.active_profile else "No profile"
        self.sidebar.refresh_profiles(names, active)

    def _on_process_status(self, payload: dict) -> None:
        """Keep status bar in sync regardless of which view is active."""
        server = payload.get("server", "")
        status = payload.get("status", "stopped")
        self.state.server_status[server] = status
        if hasattr(self, "status_bar"):
            self.status_bar.set_process_status(server, status == "running")

    def _startup_checks(self):
        """Run prerequisite checks silently on startup."""
        from core.prerequisite_manager import PrerequisiteManager
        mgr = PrerequisiteManager()
        results = mgr.check_all()
        self.state.prereq_status = {rid: r.installed for rid, r in results.items()}

    def _on_close(self):
        get_workers().shutdown()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()
