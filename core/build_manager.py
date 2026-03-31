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
        Injects BOOST_ROOT and CMAKE_SYSTEM_VERSION (Windows SDK) automatically.
        """
        opts: dict[str, str] = {}

        # Inject BOOST_ROOT if not already in the environment
        boost_root = os.environ.get("BOOST_ROOT", "")
        if not boost_root:
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

    def _detect_windows_sdk(self) -> str:
        """Return the highest Windows SDK version that MSBuild can actually use.

        SDK 10.0.26100.0 ships with Windows 11 24H2 but is NOT fully wired into
        VS 2022 when installed via Windows Update — MSBuild raises MSB8036 even
        though the headers and libs are present. Skip it and prefer the highest
        VS-Installer-managed SDK that has both Include/um/Windows.h and Lib.
        """
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        include_root = Path(pf86, "Windows Kits", "10", "Include")
        lib_root = Path(pf86, "Windows Kits", "10", "Lib")
        if not include_root.exists():
            return ""

        # Known-broken with VS 2022 when installed via Windows Update
        skip_versions = {"10.0.26100.0"}

        candidates = sorted(
            [d.name for d in include_root.iterdir()
             if d.is_dir() and d.name.startswith("10.")],
            reverse=True
        )
        for ver in candidates:
            if ver in skip_versions:
                continue
            if not (include_root / ver / "um" / "Windows.h").exists():
                continue
            if not (lib_root / ver / "um" / "x64").exists():
                continue
            return ver
        return ""

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

    def _build_env(self) -> dict:
        """Return environment for cmake/msbuild with VCTargetsPath pre-set.

        CMake probes VCTargetsPath by running MSBuild on a tiny test project.
        That probe triggers Windows SDK validation which fails when the SDK
        (10.0.26100.0) is present in the filesystem but not wired into VS.
        Setting VCTargetsPath as an env var makes CMake skip the probe entirely.
        """
        env = os.environ.copy()
        if "VCTargetsPath" not in env:
            # Try to find the VC targets path from the VS installation
            for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                candidate = Path(
                    env.get("ProgramFiles", r"C:\Program Files"),
                    "Microsoft Visual Studio", "2022", edition,
                    "MSBuild", "Microsoft", "VC", "v170"
                )
                if candidate.exists():
                    env["VCTargetsPath"] = str(candidate) + "\\"
                    break
        return env

    def _run_streaming(self, cmd: list[str], cwd: Path) -> Generator[tuple[str, str], None, None]:
        """Run command, yield (level, line) tuples."""
        env = self._build_env()
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
