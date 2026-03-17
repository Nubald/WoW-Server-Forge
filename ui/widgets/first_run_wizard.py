"""First-run wizard — guides new users through the initial setup flow."""
from __future__ import annotations

from pathlib import Path
import customtkinter as ctk
from app.constants import (
    COLOR_BG_DARK, COLOR_BG_CARD, COLOR_BG_SECONDARY, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_ERROR
)

# Steps shown in the wizard; id maps to a nav view the user lands on after closing
WIZARD_STEPS = [
    {
        "num": "1",
        "icon": "🔧",
        "title": "Install Prerequisites",
        "body": (
            "Server Forge needs Git, CMake, Visual Studio 2022 (C++ workload), "
            "MySQL 8, OpenSSL 3, and Boost 1.82+.\n\n"
            "Head to Prerequisites and click Check All. "
            "Any missing tools have an Install button that handles it automatically."
        ),
        "nav": "prerequisites",
        "action": "Go to Prerequisites",
    },
    {
        "num": "2",
        "icon": "🎮",
        "title": "Choose a Server Core",
        "body": (
            "Select which WoW server emulator you want to build. "
            "TrinityCore 3.3.5a is recommended for most users — it has the most "
            "content support and an active community.\n\n"
            "You can also pick AzerothCore, CMaNGOS, or vMaNGOS depending on your target expansion."
        ),
        "nav": "server_select",
        "action": "Choose Server",
    },
    {
        "num": "3",
        "icon": "📥",
        "title": "Download Source Code",
        "body": (
            "Server Forge will clone the server repository to your workspace directory. "
            "This requires Git and ~1–2 GB of disk space.\n\n"
            "Once cloned, you can pull updates at any time from the Source tab."
        ),
        "nav": "source",
        "action": "Go to Source",
    },
    {
        "num": "4",
        "icon": "⚙️",
        "title": "Add Modules (optional)",
        "body": (
            "Modules extend your server with extra features: Eluna Lua scripting, "
            "NPC Bots, Auction House Bot, Auto Balance, and more.\n\n"
            "You can skip this step and enable modules later — they are added before "
            "the CMake configure step."
        ),
        "nav": "modules",
        "action": "Browse Modules",
    },
    {
        "num": "5",
        "icon": "🔨",
        "title": "Compile the Server",
        "body": (
            "Click Build Server to run CMake configure and MSBuild. "
            "The first build typically takes 15–60 minutes depending on your CPU.\n\n"
            "Make sure Build Tools is checked so the map/vmap extractor executables "
            "are built — you'll need them in step 7."
        ),
        "nav": "build",
        "action": "Go to Build",
    },
    {
        "num": "6",
        "icon": "🗄️",
        "title": "Set Up Databases",
        "body": (
            "Connect to your MySQL server and click Setup All Databases. "
            "Server Forge will create the auth, characters, and world databases, "
            "import the base SQL, apply incremental updates, and register your realm.\n\n"
            "Download the latest TDB world database if prompted."
        ),
        "nav": "database",
        "action": "Go to Database",
    },
    {
        "num": "7",
        "icon": "🗺️",
        "title": "Extract Client Data",
        "body": (
            "The server needs DBC, Maps, VMaps, and optionally MMaps extracted from "
            "your WoW client.\n\n"
            "Go to Client Setup → Data Extraction, point it at your WoW client folder, "
            "and run the extractors. Then copy the output folders into your server install directory."
        ),
        "nav": "client",
        "action": "Go to Client Setup",
    },
    {
        "num": "8",
        "icon": "🚀",
        "title": "Start Your Server!",
        "body": (
            "Everything is ready. Head to Server Control and start the Auth Server first, "
            "then the World Server.\n\n"
            "Once both show Online, update your WoW client's realmlist.wtf "
            "and log in — your server is live!"
        ),
        "nav": "control",
        "action": "Go to Control Panel",
    },
]


class FirstRunWizard(ctk.CTkToplevel):
    """Guided setup wizard shown to first-time users."""

    def __init__(self, parent, on_navigate, on_close=None):
        super().__init__(parent)
        self._on_navigate = on_navigate
        self._on_close = on_close
        self._step_index = 0

        self.title("Welcome to One Click Server Forge")
        self.overrideredirect(False)
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_DARK)
        self.attributes("-topmost", True)

        w, h = 620, 540
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self._build_ui()
        self._show_step(0)

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, corner_radius=0, height=72)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="⚔  Welcome to Server Forge",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=COLOR_ACCENT).place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(hdr, text="Let's get your WoW server running in 8 steps",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLOR_TEXT_SECONDARY).place(relx=0.5, rely=0.75, anchor="center")

        # Step progress pills
        pills_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_SECONDARY, corner_radius=0, height=44)
        pills_frame.pack(fill="x")
        pills_frame.pack_propagate(False)
        self._pills: list[ctk.CTkLabel] = []
        pills_inner = ctk.CTkFrame(pills_frame, fg_color="transparent")
        pills_inner.place(relx=0.5, rely=0.5, anchor="center")
        for i, step in enumerate(WIZARD_STEPS):
            pill = ctk.CTkLabel(
                pills_inner, text=step["num"], width=26, height=26,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                fg_color=COLOR_BORDER, corner_radius=13,
                text_color=COLOR_TEXT_MUTED
            )
            pill.pack(side="left", padx=3)
            self._pills.append(pill)
            if i < len(WIZARD_STEPS) - 1:
                ctk.CTkLabel(pills_inner, text="—", font=ctk.CTkFont("Segoe UI", 9),
                             text_color=COLOR_BORDER).pack(side="left")

        # Content area
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=32, pady=16)

        self._icon_lbl = ctk.CTkLabel(self._content, text="",
                                      font=ctk.CTkFont("Segoe UI", 40))
        self._icon_lbl.pack(pady=(8, 0))

        self._step_num_lbl = ctk.CTkLabel(self._content, text="",
                                          font=ctk.CTkFont("Segoe UI", 10),
                                          text_color=COLOR_TEXT_MUTED)
        self._step_num_lbl.pack()

        self._title_lbl = ctk.CTkLabel(self._content, text="",
                                       font=ctk.CTkFont("Segoe UI", 18, "bold"),
                                       text_color=COLOR_TEXT_PRIMARY)
        self._title_lbl.pack(pady=(4, 8))

        self._body_lbl = ctk.CTkLabel(
            self._content, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=540, justify="left"
        )
        self._body_lbl.pack(fill="x")

        # Bottom button row
        ctk.CTkFrame(self, fg_color=COLOR_BORDER, height=1).pack(fill="x")
        btn_row = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, height=56, corner_radius=0)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        btn_inner = ctk.CTkFrame(btn_row, fg_color="transparent")
        btn_inner.place(relx=0.5, rely=0.5, anchor="center")

        self._prev_btn = ctk.CTkButton(
            btn_inner, text="◀  Back", width=100, height=34,
            fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_SECONDARY, font=ctk.CTkFont("Segoe UI", 11),
            command=self._prev
        )
        self._prev_btn.pack(side="left", padx=4)

        self._nav_btn = ctk.CTkButton(
            btn_inner, text="Go to Prerequisites", width=180, height=34,
            fg_color=COLOR_BG_SECONDARY, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_SECONDARY, font=ctk.CTkFont("Segoe UI", 11),
            command=self._go_to_step_view
        )
        self._nav_btn.pack(side="left", padx=4)

        self._next_btn = ctk.CTkButton(
            btn_inner, text="Next  ▶", width=100, height=34,
            fg_color=COLOR_ACCENT, hover_color="#58a6ff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._next
        )
        self._next_btn.pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row, text="Skip wizard", width=90, height=28,
            fg_color="transparent", hover_color=COLOR_BG_SECONDARY,
            text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont("Segoe UI", 9),
            command=self._close
        ).place(relx=0.98, rely=0.5, anchor="e")

    def _show_step(self, index: int):
        self._step_index = index
        step = WIZARD_STEPS[index]

        # Update pills
        for i, pill in enumerate(self._pills):
            if i < index:
                pill.configure(fg_color=COLOR_SUCCESS, text_color="white")
            elif i == index:
                pill.configure(fg_color=COLOR_ACCENT, text_color="white")
            else:
                pill.configure(fg_color=COLOR_BORDER, text_color=COLOR_TEXT_MUTED)

        self._icon_lbl.configure(text=step["icon"])
        self._step_num_lbl.configure(text=f"Step {step['num']} of {len(WIZARD_STEPS)}")
        self._title_lbl.configure(text=step["title"])
        self._body_lbl.configure(text=step["body"])
        self._nav_btn.configure(text=step["action"])

        self._prev_btn.configure(state="normal" if index > 0 else "disabled")
        is_last = index == len(WIZARD_STEPS) - 1
        self._next_btn.configure(
            text="Finish ✓" if is_last else "Next  ▶",
            fg_color=COLOR_SUCCESS if is_last else COLOR_ACCENT,
            hover_color="#45c55a" if is_last else "#58a6ff",
        )

    def _prev(self):
        if self._step_index > 0:
            self._show_step(self._step_index - 1)

    def _next(self):
        if self._step_index < len(WIZARD_STEPS) - 1:
            self._show_step(self._step_index + 1)
        else:
            self._close()

    def _go_to_step_view(self):
        step = WIZARD_STEPS[self._step_index]
        self._on_navigate(step["nav"])
        self._close()

    def _close(self):
        self.grab_release()
        self.destroy()
        if self._on_close:
            self._on_close()
