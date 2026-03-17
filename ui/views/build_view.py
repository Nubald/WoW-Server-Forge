"""Build / compile view — CMake configure + compile with live logs."""
from __future__ import annotations

import shutil
import time
from pathlib import Path
import customtkinter as ctk
from ui.views.base_view import BaseView
from ui.widgets.log_console import LogConsole
from core.build_manager import BuildManager
from core.module_manager import ModuleManager
from services.worker_service import get_workers
from app.constants import (
    COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, BUILD_TYPES
)

STEPS = ["configure", "compile", "install"]


class StepIndicator(ctk.CTkFrame):
    def __init__(self, master, label: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._dot = ctk.CTkLabel(self, text="○",
                                 font=ctk.CTkFont("Segoe UI", 18),
                                 text_color=COLOR_TEXT_MUTED, width=28)
        self._dot.pack(side="left")
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.pack(side="left", padx=6)
        ctk.CTkLabel(col, text=label, font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(anchor="w")
        self._time_lbl = ctk.CTkLabel(col, text="",
                                      font=ctk.CTkFont("Segoe UI", 9),
                                      text_color=COLOR_TEXT_MUTED, anchor="w")
        self._time_lbl.pack(anchor="w")

    def set_status(self, status: str, elapsed: str = ""):
        configs = {
            "idle":    ("○", COLOR_TEXT_MUTED),
            "running": ("⟳", COLOR_WARNING),
            "done":    ("✓", COLOR_SUCCESS),
            "error":   ("✗", COLOR_ERROR),
        }
        text, color = configs.get(status, ("○", COLOR_TEXT_MUTED))
        self._dot.configure(text=text, text_color=color)
        if elapsed:
            self._time_lbl.configure(text=elapsed)


class BuildView(BaseView):

    def build_ui(self):
        self._header(self, "Compile Server",
                     "Configure CMake and compile the server binary")
        self._build_mgr = BuildManager()
        self._mod_mgr = ModuleManager()
        self._build_start: float = 0
        self._step_times: dict[str, float] = {}
        self._indicators: dict[str, StepIndicator] = {}
        self._cancelled = False

        # ── Options panel ─────────────────────────────────────────────
        opts_outer = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=8)
        opts_outer.pack(fill="x", padx=24, pady=(8, 0))

        opts_toggle = ctk.CTkButton(
            opts_outer, text="▼  Build Options", anchor="w",
            fg_color="transparent", hover_color=COLOR_BG_CARD,
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._toggle_options
        )
        opts_toggle.pack(fill="x", padx=4, pady=4)

        self._opts_frame = ctk.CTkFrame(opts_outer, fg_color="transparent")
        self._opts_frame.pack(fill="x", padx=14, pady=(0, 10))

        row1 = ctk.CTkFrame(self._opts_frame, fg_color="transparent")
        row1.pack(fill="x", pady=2)

        ctk.CTkLabel(row1, text="Build Type:", font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY, width=100, anchor="w").pack(side="left")
        self._build_type_var = ctk.StringVar(value="RelWithDebInfo")
        ctk.CTkOptionMenu(
            row1, variable=self._build_type_var, values=BUILD_TYPES,
            width=160, height=28,
            fg_color="#21262d", button_color=COLOR_ACCENT,
            font=ctk.CTkFont("Segoe UI", 11)
        ).pack(side="left", padx=8)

        ctk.CTkLabel(row1, text="Threads:", font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY, width=70, anchor="w").pack(side="left", padx=(16, 0))
        self._jobs_entry = ctk.CTkEntry(row1, width=50, height=28, placeholder_text="auto",
                                        fg_color="#0d1117", border_color=COLOR_BORDER,
                                        text_color=COLOR_TEXT_PRIMARY)
        self._jobs_entry.pack(side="left", padx=4)

        row2 = ctk.CTkFrame(self._opts_frame, fg_color="transparent")
        row2.pack(fill="x", pady=4)

        self._tools_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row2, text="Build Tools (map/vmap extractors)",
                        variable=self._tools_var,
                        font=ctk.CTkFont("Segoe UI", 11),
                        text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 16))

        self._pch_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row2, text="Precompiled Headers (faster builds)",
                        variable=self._pch_var,
                        font=ctk.CTkFont("Segoe UI", 11),
                        text_color=COLOR_TEXT_SECONDARY).pack(side="left")

        # ── Step indicators ───────────────────────────────────────────
        steps_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, corner_radius=8)
        steps_frame.pack(fill="x", padx=24, pady=12)

        step_inner = ctk.CTkFrame(steps_frame, fg_color="transparent")
        step_inner.pack(fill="x", padx=14, pady=10)

        step_labels = {"configure": "CMake Configure", "compile": "Compile", "install": "Install"}
        for i, (sid, slabel) in enumerate(step_labels.items()):
            ind = StepIndicator(step_inner, slabel)
            ind.pack(side="left", expand=True, fill="x")
            self._indicators[sid] = ind
            if i < len(step_labels) - 1:
                ctk.CTkLabel(step_inner, text="→", font=ctk.CTkFont("Segoe UI", 14),
                             text_color=COLOR_TEXT_MUTED).pack(side="left", padx=4)

        # ── Action buttons ────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 8))

        self._build_btn = ctk.CTkButton(
            btn_row, text="▶  Build Server", height=40, width=160,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=self._start_build
        )
        self._build_btn.pack(side="left")

        self._cancel_btn = ctk.CTkButton(
            btn_row, text="■  Cancel", height=40, width=100,
            fg_color=COLOR_ERROR, hover_color="#ff6b6b",
            font=ctk.CTkFont("Segoe UI", 13),
            state="disabled",
            command=self._cancel_build
        )
        self._cancel_btn.pack(side="left", padx=8)

        self._clear_cache_btn = ctk.CTkButton(
            btn_row, text="Clear Cache", height=40, width=110,
            fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BG_CARD,
            border_width=1, border_color=COLOR_BORDER,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLOR_TEXT_SECONDARY,
            command=self._clear_cmake_cache
        )
        self._clear_cache_btn.pack(side="left", padx=4)

        self._elapsed_lbl = ctk.CTkLabel(
            btn_row, text="",
            font=ctk.CTkFont("Consolas", 11),
            text_color=COLOR_TEXT_SECONDARY
        )
        self._elapsed_lbl.pack(side="left", padx=8)

        self._next_btn = ctk.CTkButton(
            btn_row, text="Next: Database  →", height=40, width=160,
            fg_color=COLOR_SUCCESS, hover_color="#45c55a",
            font=ctk.CTkFont("Segoe UI", 12),
            state="disabled",
            command=lambda: self.app.show_view("database")
        )
        self._next_btn.pack(side="right")

        # ── Log console ───────────────────────────────────────────────
        self._log = LogConsole(self)
        self._log.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        self._opts_visible = True

    def _toggle_options(self):
        if self._opts_visible:
            self._opts_frame.pack_forget()
            self._opts_visible = False
        else:
            self._opts_frame.pack(fill="x", padx=14, pady=(0, 10))
            self._opts_visible = True

    def _start_build(self):
        profile = self.state.active_profile
        if not profile:
            self._log.append("[ERROR] No active profile selected", "error")
            return
        source_dir = self.app.get_source_dir()
        if not source_dir or not source_dir.exists():
            self._log.append("[ERROR] Source not cloned. Go to 'Source Code' tab first.", "error")
            return

        # ── Pre-configure checks (runs on main thread — fast registry/file checks) ──
        problems = self._build_mgr.pre_check()
        if problems:
            self._log.clear()
            self._log.append("═══ Pre-Build Check Failed ═══════════════════════════", "error")
            for level, msg in problems:
                for line in msg.splitlines():
                    self._log.append(f"  {line}", level)
            self._log.append("", "info")
            self._log.append("Fix the issue above, then click Build again.", "warning")
            self._log.append("→ Go to the Prerequisites tab to install missing components.", "info")
            return

        self._build_btn.configure(state="disabled", text="Building...")
        self._cancel_btn.configure(state="normal")
        self._next_btn.configure(state="disabled")
        for ind in self._indicators.values():
            ind.set_status("idle")
        self._log.clear()
        self._build_start = time.time()
        self._cancelled = False
        self._update_timer()
        get_workers().submit("build", self._do_build, profile, source_dir)

    def _do_build(self, profile, source_dir):
        build_dir = Path(profile.build_dir)
        install_dir = Path(profile.install_dir)
        build_type = self._build_type_var.get()

        jobs_text = self._jobs_entry.get().strip()
        jobs = int(jobs_text) if jobs_text.isdigit() else 0

        # Collect CMake options
        sdef = self.app.get_server_def(profile.server_id) or {}
        cmake_opts = dict(sdef.get("build", {}).get("default_options", {}))
        cmake_opts["CMAKE_INSTALL_PREFIX"] = str(install_dir)
        cmake_opts["TOOLS"] = "ON" if self._tools_var.get() else "OFF"
        cmake_opts["USE_COREPCH"] = "ON" if self._pch_var.get() else "OFF"
        cmake_opts["CMAKE_BUILD_TYPE"] = build_type

        # Module CMake options
        mod_opts = self._mod_mgr.get_cmake_options(set(profile.enabled_modules))
        cmake_opts.update(mod_opts)
        cmake_opts.update(profile.cmake_extra_options)

        success = True
        # Configure
        t0 = time.time()
        for level, line in self._build_mgr.configure(source_dir, build_dir, cmake_opts):
            if self._cancelled:
                return
            self.after(0, lambda l=line, lv=level: self._log.append(l, lv))
            if level == "error":
                success = False
        self.after(0, lambda e=f"{time.time()-t0:.0f}s":
                   self._indicators["configure"].set_status(
                       "done" if success else "error", e))

        if not success:
            self.after(0, self._on_build_failed)
            return

        # Compile
        t0 = time.time()
        for level, line in self._build_mgr.compile(build_dir, build_type, jobs):
            if self._cancelled:
                return
            self.after(0, lambda l=line, lv=level: self._log.append(l, lv))
            if level == "error":
                success = False
        self.after(0, lambda e=f"{time.time()-t0:.0f}s":
                   self._indicators["compile"].set_status(
                       "done" if success else "error", e))

        if not success:
            self.after(0, self._on_build_failed)
            return

        # Install
        t0 = time.time()
        for level, line in self._build_mgr.install(build_dir, install_dir, build_type):
            self.after(0, lambda l=line, lv=level: self._log.append(l, lv))
        self.after(0, lambda e=f"{time.time()-t0:.0f}s":
                   self._indicators["install"].set_status("done", e))

        self.after(0, self._on_build_success)

    def _on_build_success(self):
        self._build_btn.configure(state="normal", text="▶  Build Server")
        self._cancel_btn.configure(state="disabled")
        self._next_btn.configure(state="normal")
        self._log.append("═══════════════════════════════", "success")
        self._log.append("  BUILD COMPLETE — SUCCESS  ✓  ", "success")
        self._log.append("═══════════════════════════════", "success")
        self.app.status_bar.set_build_status("SUCCESS")
        self.bus.emit("build.complete", {"success": True})

    def _on_build_failed(self):
        self._build_btn.configure(state="normal", text="▶  Build Server")
        self._cancel_btn.configure(state="disabled")
        self._log.append("═══════════════════════════════", "error")
        self._log.append("  BUILD FAILED  ✗             ", "error")
        self._log.append("═══════════════════════════════", "error")
        self.app.status_bar.set_build_status("FAILED")
        self.bus.emit("build.complete", {"success": False})

    def _cancel_build(self):
        self._cancelled = True
        self._build_mgr.cancel()
        self._build_btn.configure(state="normal", text="▶  Build Server")
        self._cancel_btn.configure(state="disabled")
        self._log.append("[CANCELLED] Build cancelled by user", "warning")

    def _clear_cmake_cache(self):
        profile = self.state.active_profile
        if not profile:
            self._log.append("[ERROR] No active profile — nothing to clear", "error")
            return
        build_dir = Path(profile.build_dir)
        cache_file = build_dir / "CMakeCache.txt"
        cmake_files = build_dir / "CMakeFiles"
        cleared = []
        if cache_file.exists():
            cache_file.unlink()
            cleared.append("CMakeCache.txt")
        if cmake_files.exists():
            shutil.rmtree(cmake_files, ignore_errors=True)
            cleared.append("CMakeFiles/")
        if cleared:
            self._log.append(f"[OK] Cleared: {', '.join(cleared)}", "success")
            self._log.append("[INFO] Next build will run a full CMake configure.", "info")
            for ind in self._indicators.values():
                ind.set_status("idle")
        else:
            self._log.append("[INFO] No CMake cache found — build directory may be clean.", "info")

    def _update_timer(self):
        if self._build_start and get_workers().is_running("build"):
            elapsed = time.time() - self._build_start
            self._elapsed_lbl.configure(text=f"⏱ {elapsed:.0f}s")
            self.after(1000, self._update_timer)
        else:
            self._elapsed_lbl.configure(text="")

    def _subscribe_events(self):
        self.bus.subscribe("build.step_changed", self._on_step)

    def _unsubscribe_events(self):
        self.bus.unsubscribe("build.step_changed", self._on_step)

    def _on_step(self, payload: dict):
        step = payload.get("step", "")
        status = payload.get("status", "idle")
        if step in self._indicators:
            self._indicators[step].set_status(status)
