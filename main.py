#!/usr/bin/env python3
"""
One Click Server Forge
======================
A comprehensive World of Warcraft private server compilation and management tool.

Usage:
    python main.py

Requirements:
    pip install -r requirements.txt
"""
import sys
import os

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_python_version():
    if sys.version_info < (3, 10):
        print("ERROR: Python 3.10+ is required.")
        print(f"       You have: Python {sys.version}")
        sys.exit(1)


def check_dependencies():
    missing = []
    required = ["customtkinter", "requests", "psutil", "packaging"]
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print("Missing required packages. Run:")
        print("    pip install -r requirements.txt")
        print(f"\nMissing: {', '.join(missing)}")
        # Try to auto-install
        response = input("\nAuto-install now? [y/N]: ").strip().lower()
        if response == "y":
            import subprocess
            req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])
        else:
            sys.exit(1)


def main():
    check_python_version()
    check_dependencies()

    # Launch the application — it owns the single CTk root.
    # The splash is shown on the real root to avoid destroyed-widget after() errors.
    from app.application import ForgeApplication
    app = ForgeApplication()
    app.run()


if __name__ == "__main__":
    main()
