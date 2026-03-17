"""App-wide constants for One Click Server Forge."""
from pathlib import Path

APP_NAME = "One Click Server Forge"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Server Forge"

# Paths
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
PROFILES_DIR = ROOT_DIR / "profiles"
LOGS_DIR = ROOT_DIR / "logs"

SERVERS_DIR = DATA_DIR / "servers"
MODULES_DIR = DATA_DIR / "modules"
PREREQS_DIR = DATA_DIR / "prerequisites"
TEMPLATES_DIR = DATA_DIR / "templates"
CLIENT_INFO_DIR = DATA_DIR / "client_info"

# UI Dimensions
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
SIDEBAR_WIDTH = 220
MIN_WIDTH = 1100
MIN_HEIGHT = 700

# Colors
COLOR_BG_DARK       = "#0d1117"
COLOR_BG_SECONDARY  = "#161b22"
COLOR_BG_CARD       = "#1c2128"
COLOR_BG_HOVER      = "#21262d"
COLOR_BORDER        = "#30363d"

COLOR_TEXT_PRIMARY   = "#e6edf3"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_TEXT_MUTED     = "#484f58"

COLOR_ACCENT         = "#388bfd"
COLOR_ACCENT_HOVER   = "#58a6ff"
COLOR_SUCCESS        = "#3fb950"
COLOR_WARNING        = "#d29922"
COLOR_ERROR          = "#f85149"
COLOR_INFO           = "#58a6ff"

COLOR_SIDEBAR_BG     = "#010409"
COLOR_SIDEBAR_SELECT = "#1c2128"

# Nav sections
NAV_SECTIONS = [
    {
        "label": "OVERVIEW",
        "items": [
            {"id": "dashboard",    "label": "Dashboard",     "icon": "⬡"},
        ]
    },
    {
        "label": "SETUP",
        "items": [
            {"id": "prerequisites","label": "Prerequisites",  "icon": "⚙"},
            {"id": "server_select","label": "Server / Core",  "icon": "⊞"},
            {"id": "source",       "label": "Source Code",    "icon": "⌥"},
            {"id": "modules",      "label": "Modules",        "icon": "⊕"},
        ]
    },
    {
        "label": "BUILD & CONFIGURE",
        "items": [
            {"id": "build",        "label": "Compile",        "icon": "▶"},
            {"id": "database",     "label": "Database",       "icon": "⊟"},
            {"id": "config",       "label": "Configuration",  "icon": "≡"},
            {"id": "ports",        "label": "Ports & Network","icon": "⊷"},
        ]
    },
    {
        "label": "SERVER",
        "items": [
            {"id": "control",      "label": "Control Panel",  "icon": "◉"},
            {"id": "client",       "label": "Client Info",    "icon": "⬇"},
        ]
    },
]

# Build types
BUILD_TYPES = ["RelWithDebInfo", "Release", "Debug"]

# Default ports
DEFAULT_PORTS = {
    "auth_port":    3724,
    "world_port":   8085,
    "mysql_port":   3306,
    "soap_port":    7878,
    "ra_port":      3443,
}
