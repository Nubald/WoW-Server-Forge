"""CMake configure + MSBuild compile pipeline with live log streaming."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

from services.event_bus import get_bus
from services.log_service import get_log


@dataclass
class BuildResult:
    success: bool = False
    errors: int = 0
    warnings: int = 0
    duration_seconds: float = 0.0
    message: str = ""
    install_dir: str = ""


class BuildManager:
    """Orchestrates CMake configuration and MSBuild/Ninja compilation."""

    def __init__(self):
        self._bus = get_bus()
        self._log = get_log()
        self._cancel_flag = False

    def cancel(self) -> None:
        self._cancel_flag = True

    def _find_cmake(self) -> str:
        candidates = [
            "cmake",
            r"C:\Program Files\CMake\bin\cmake.exe",
            r"C:\Program Files (x86)\CMake\bin\cmake.exe",
        ]
        for c in candidates:
            try:
                subprocess.run([c, "--version"], capture_output=True, timeout=5)
                return c
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return "cmake"

    def pre_check(self) -> list[tuple[str, str]]:
        """Run pre-configure sanity checks. Returns list of (level, message) problems."""
        problems = []

        vswhere = Path(
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            "Microsoft Visual Studio", "Installer", "vswhere.exe"
        )

        if not vswhere.exists():
            problems.append(("error",
                "Visual Studio Installer not found. "
                "Install Visual Studio 2022 via the Prerequisites tab."))
            return problems

        # Get VS install path
        try:
            r = subprocess.run(
                [str(vswhere), "-latest", "-property", "installationPath"],
                capture_output=True, text=True, timeout=10
            )
            install_path = r.stdout.strip()
        except Exception:
            install_path = ""

        if not install_path:
            problems.append(("error",
                "Visual Studio 2022 not found. "
                "Install it via the Prerequisites tab."))
            return problems

        # Check the critical C++ targets file that causes this exact CMake error
        cpp_targets = Path(install_path) / "MSBuild" / "Microsoft" / "VC" / "v170" / "Microsoft.CppCommon.targets"
        if not cpp_targets.exists():
            problems.append(("error",
                "C++ build tools are missing from your Visual Studio installation.\n"
                "  Fix: Open 'Visual Studio Installer' → Modify your VS 2022 install\n"
                "       → Check 'Desktop development with C++' → Click Modify.\n"
                "  Or:  Go to Prerequisites tab and click Install next to Visual Studio."))

        # Check CMake is reachable
        cmake = self._find_cmake()
        try:
            subprocess.run([cmake, "--version"], capture_output=True, timeout=5)
        except FileNotFoundError:
            problems.append(("error",
                "CMake not found. Install it via the Prerequisites tab."))

        return problems

    def _auto_cmake_options(self) -> dict[str, str]:
        """Return CMake -D options that can be inferred from the local environment.

        These act as safe defaults — the caller's explicit options always win.
        Currently injects BOOST_ROOT when the env var or a known install path is set.
        """
        opts: dict[str, str] = {}

        # Inject BOOST_ROOT if not already in the environment
        boost_root = os.environ.get("BOOST_ROOT", "")
        if not boost_root:
            # Try known default install paths used by our own installer
            for candidate in [
                r"C:\local\boost_1_86_0",
                r"C:\local\boost_1_85_0",
                r"C:\local\boost_1_84_0",
                r"C:\local\boost_1_83_0",
                r"C:\local\boost_1_82_0",
                r"C:\boost",
            ]:
                if (Path(candidate) / "boost" / "version.hpp").exists():
                    boost_root = candidate
                    break

        if boost_root:
            opts["BOOST_ROOT"] = boost_root

        return opts

    def _find_msbuild(self) -> str:
        # Use vswhere to locate MSBuild
        vswhere = Path(
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            "Microsoft Visual Studio", "Installer", "vswhere.exe"
        )
        if vswhere.exists():
            try:
                r = subprocess.run(
                    [str(vswhere), "-latest", "-requires",
                     "Microsoft.Component.MSBuild",
                     "-find", r"MSBuild\**\Bin\MSBuild.exe"],
                    capture_output=True, text=True, timeout=10
                )
                path = r.stdout.strip()
                if path and Path(path).exists():
                    return path
            except Exception:
                pass
        return "msbuild"

    def _run_streaming(self, cmd: list[str], cwd: Path) -> Generator[tuple[str, str], None, None]:
        """Run command, yield (level, line) tuples."""
        env = os.environ.copy()
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(cwd),
                encoding="utf-8", errors="replace", env=env
            )
            for line in proc.stdout:
                if self._cancel_flag:
                    proc.terminate()
                    yield ("warn", "[CANCELLED] Build cancelled by user")
                    return
                line = line.rstrip()
                if not line:
                    continue
                level = self._classify_line(line)
                self._bus.emit("build.log_line", {"level": level, "text": line})
                yield (level, line)
            proc.wait()
            if proc.returncode != 0 and not self._cancel_flag:
                msg = f"[EXIT {proc.returncode}] Process exited with error"
                self._bus.emit("build.log_line", {"level": "error", "text": msg})
                yield ("error", msg)
        except FileNotFoundError as e:
            msg = f"[ERROR] {e}"
            self._bus.emit("build.log_line", {"level": "error", "text": msg})
            yield ("error", msg)

    def _classify_line(self, line: str) -> str:
        lower = line.lower()
        if any(k in lower for k in ["error", "failed", "fatal"]):
            if "warning treated as error" not in lower:
                return "error"
        if "warning" in lower:
            return "warning"
        if any(k in lower for k in ["-- ", "configuring", "generating", "build files"]):
            return "cmake"
        return "info"

    def configure(self, source_dir: Path, build_dir: Path,
                  options: dict[str, str]) -> Generator[tuple[str, str], None, None]:
        """Run cmake configure step."""
        self._cancel_flag = False
        build_dir.mkdir(parents=True, exist_ok=True)
        cmake = self._find_cmake()

        # Merge options: caller-supplied values take priority over auto-detected ones
        effective_options = self._auto_cmake_options()
        effective_options.update(options)

        cmd = [cmake, str(source_dir), "-A", "x64"]
        for key, val in effective_options.items():
            cmd.append(f"-D{key}={val}")

        self._bus.emit("build.step_changed", {"step": "configure", "status": "running"})
        yield ("info", f"[CMAKE] Configuring: {' '.join(cmd[:6])}...")
        yield from self._run_streaming(cmd, build_dir)
        self._bus.emit("build.step_changed", {"step": "configure", "status": "done"})

    def compile(self, build_dir: Path, config: str = "RelWithDebInfo",
                jobs: int = 0) -> Generator[tuple[str, str], None, None]:
        """Run cmake --build (uses MSBuild/Ninja under the hood)."""
        self._cancel_flag = False
        cmake = self._find_cmake()
        cpu_count = os.cpu_count() or 4
        j = jobs if jobs > 0 else cpu_count

        cmd = [cmake, "--build", str(build_dir),
               "--config", config,
               "--parallel", str(j)]

        self._bus.emit("build.step_changed", {"step": "compile", "status": "running"})
        yield ("info", f"[BUILD] Compiling with {j} threads (config: {config})...")
        yield from self._run_streaming(cmd, build_dir)
        self._bus.emit("build.step_changed", {"step": "compile", "status": "done"})

    def install(self, build_dir: Path, install_dir: Path,
                config: str = "RelWithDebInfo") -> Generator[tuple[str, str], None, None]:
        """Run cmake --install to copy binaries."""
        cmake = self._find_cmake()
        install_dir.mkdir(parents=True, exist_ok=True)
        cmd = [cmake, "--install", str(build_dir),
               "--config", config,
               "--prefix", str(install_dir)]

        self._bus.emit("build.step_changed", {"step": "install", "status": "running"})
        yield ("info", f"[INSTALL] Installing to {install_dir}...")
        yield from self._run_streaming(cmd, build_dir)
        self._bus.emit("build.step_changed", {"step": "install", "status": "done"})
