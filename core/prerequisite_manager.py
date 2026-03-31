"""Detect and install prerequisites (Git, CMake, VS Build Tools, MySQL, OpenSSL, Boost)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

from packaging.version import Version

from app.constants import PREREQS_DIR
from services.event_bus import get_bus
from services.log_service import get_log


@dataclass
class PrereqResult:
    id: str
    display_name: str
    installed: bool
    version: str = ""
    path: str = ""
    message: str = ""


class PrerequisiteManager:
    """Checks for and optionally installs all required build tools."""

    def __init__(self):
        self._bus = get_bus()
        self._log = get_log()
        self._requirements = self._load_requirements()

    def _load_requirements(self) -> list[dict]:
        req_file = PREREQS_DIR / "windows_requirements.json"
        if req_file.exists():
            return json.loads(req_file.read_text(encoding="utf-8")).get("requirements", [])
        return []

    # ── Public API ────────────────────────────────────────────────────

    def check_all(self) -> dict[str, PrereqResult]:
        results: dict[str, PrereqResult] = {}
        with ThreadPoolExecutor(max_workers=len(self._requirements) or 1) as pool:
            future_to_req = {pool.submit(self._check_one, req): req for req in self._requirements}
            for future in as_completed(future_to_req):
                result = future.result()
                results[result.id] = result
                self._bus.emit("prereq.checked", result)
        # Return in original order
        return {req["id"]: results[req["id"]] for req in self._requirements if req["id"] in results}

    def check(self, req_id: str) -> Optional[PrereqResult]:
        for req in self._requirements:
            if req["id"] == req_id:
                return self._check_one(req)
        return None

    def install(self, req_id: str) -> Generator[str, None, None]:
        """Install a prerequisite. Yields log lines."""
        req = next((r for r in self._requirements if r["id"] == req_id), None)
        if not req:
            yield f"[ERROR] Unknown prerequisite: {req_id}"
            return

        if req_id == "git":
            yield from self._install_git(req)
        elif req_id == "cmake":
            yield from self._install_cmake(req)
        elif req_id == "mysql":
            yield from self._install_mysql(req)
        elif req_id == "openssl":
            yield from self._install_openssl(req)
        elif req_id == "boost":
            yield from self._install_boost(req)
        else:
            yield from self._install_winget(req)

    def get_requirements(self) -> list[dict]:
        return self._requirements

    # ── Detection ─────────────────────────────────────────────────────

    def _check_one(self, req: dict) -> PrereqResult:
        rid = req["id"]
        name = req["display_name"]

        if rid == "visual_studio":
            return self._check_vs(req)
        if rid == "boost":
            return self._check_boost(req)
        if rid == "mysql":
            return self._check_mysql(req)
        if rid == "openssl":
            return self._check_openssl(req)

        cmd = req.get("check_command")
        if not cmd:
            return PrereqResult(rid, name, False, message="No check command defined")

        # Build a PATH that includes all known hint locations for this tool
        env = self._env_with_hints(req)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, env=env
            )
            output = (result.stdout + result.stderr).strip()
            version = self._parse_version(output, req.get("version_regex", ""))

            min_ver = req.get("min_version", "0.0.0")
            ok = self._version_ok(version, min_ver)

            found_path = shutil.which(cmd[0], path=env.get("PATH", "")) or ""
            return PrereqResult(
                rid, name, ok,
                version=version,
                path=found_path,
                message="" if ok else (
                    f"Found {version}, need {min_ver}+" if version else "Not found in PATH"
                )
            )
        except FileNotFoundError:
            return PrereqResult(rid, name, False, message="Not found in PATH")
        except subprocess.TimeoutExpired:
            return PrereqResult(rid, name, False, message="Check timed out")
        except Exception as e:
            return PrereqResult(rid, name, False, message=str(e))

    def _check_vs(self, req: dict) -> PrereqResult:
        name = req["display_name"]
        vswhere = self._find_vswhere()

        if vswhere:
            # ── Step 1: check VS version ──────────────────────────────
            ver = self._vswhere_query(vswhere, ["-latest", "-property", "installationVersion"])
            if ver:
                major = int(ver.split(".")[0])
                if major < 17:
                    return PrereqResult("visual_studio", name, False, version=ver,
                                       message=f"Found VS {ver}, need 2022 (v17+)")

                # ── Step 2: check C++ workload is installed ────────────
                install_path = self._vswhere_query(
                    vswhere, ["-latest", "-property", "installationPath"]
                )
                if install_path:
                    cpp_ok, cpp_msg = self._check_cpp_targets(Path(install_path))
                    if not cpp_ok:
                        return PrereqResult(
                            "visual_studio", name, False, version=ver,
                            path=install_path, message=cpp_msg
                        )
                    return PrereqResult("visual_studio", name, True, version=ver,
                                       path=install_path)

                # vswhere found VS but couldn't get path — fallback check
                cpp_tools = self._vswhere_query(
                    vswhere,
                    ["-latest", "-requires",
                     "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                     "-property", "installationVersion"]
                )
                if cpp_tools:
                    return PrereqResult("visual_studio", name, True, version=ver)
                return PrereqResult(
                    "visual_studio", name, False, version=ver,
                    message="C++ Desktop workload missing — click Install to add it"
                )

        # Registry fallback (older detection path)
        if winreg is not None:
            for key_path in [
                r"SOFTWARE\Microsoft\VisualStudio\17.0",
                r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\17.0",
            ]:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path):
                        return PrereqResult("visual_studio", name, True, version="17.x")
                except FileNotFoundError:
                    continue

        return PrereqResult("visual_studio", name, False,
                            message="Visual Studio 2022 not found")

    def _find_vswhere(self) -> Optional[Path]:
        vswhere = Path(
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            "Microsoft Visual Studio", "Installer", "vswhere.exe"
        )
        return vswhere if vswhere.exists() else None

    def _vswhere_query(self, vswhere: Path, extra_args: list[str]) -> str:
        try:
            r = subprocess.run(
                [str(vswhere)] + extra_args,
                capture_output=True, text=True, timeout=15
            )
            return r.stdout.strip()
        except Exception:
            return ""

    def _check_cpp_targets(self, install_path: Path) -> tuple[bool, str]:
        """Verify the C++ MSBuild targets exist in the VS installation."""
        # These paths must exist for CMake + MSBuild C++ projects to work
        checks = [
            install_path / "MSBuild" / "Microsoft" / "VC" / "v170" / "Microsoft.CppCommon.targets",
            install_path / "MSBuild" / "Microsoft" / "VC" / "v170" / "Microsoft.CppBuild.targets",
        ]
        missing = [p for p in checks if not p.exists()]
        if missing:
            return False, (
                "C++ build tools incomplete — Microsoft.CppCommon.targets missing. "
                "Click Install to add the 'Desktop development with C++' workload."
            )
        return True, ""

    def _check_boost(self, req: dict) -> PrereqResult:
        name = req["display_name"]
        # Gather candidate directories: env var + all path hints
        candidates = []
        env_val = os.environ.get(req.get("env_var", "BOOST_ROOT"), "")
        if env_val:
            candidates.append(Path(env_val))
        for hint in req.get("path_hints", []):
            candidates.append(Path(hint))

        for p in candidates:
            if not p.exists():
                continue
            # version.hpp is at <boost_root>/boost/version.hpp
            version_hpp = p / "boost" / "version.hpp"
            if not version_hpp.exists():
                # Maybe a parent dir was given — search one level deeper
                matches = list(p.glob("*/boost/version.hpp"))
                if matches:
                    version_hpp = matches[0]
                    p = version_hpp.parent.parent

            if version_hpp.exists():
                content = version_hpp.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"#define BOOST_LIB_VERSION\s+\"([\d_]+)\"", content)
                ver = m.group(1).replace("_", ".") if m else "found"
                min_ver = req.get("min_version", "0")
                ok = self._version_ok(ver, min_ver)
                return PrereqResult(
                    "boost", name, ok, version=ver, path=str(p),
                    message="" if ok else f"Found {ver}, need {min_ver}+"
                )

        return PrereqResult(
            "boost", name, False,
            message="Not found. Use Install button to download pre-built binaries."
        )

    # ── Installation ──────────────────────────────────────────────────

    def _install_winget(self, req: dict) -> Generator[str, None, None]:
        """Generic winget install — with special handling for Visual Studio."""
        winget_id = req.get("winget_id")
        if not winget_id:
            yield f"[ERROR] No winget ID for {req['display_name']}"
            yield f"[INFO]  Manual download: {req.get('fallback_url', '')}"
            return

        if req["id"] == "visual_studio":
            yield from self._install_vs_cpp(req, winget_id)
            return

        if not self._winget_available():
            yield "[WARN] winget is not available on this system."
            yield f"[INFO] Please install {req['display_name']} manually:"
            yield f"[INFO]   {req.get('fallback_url', '')}"
            self._open_url(req.get("fallback_url", ""))
            return

        yield f"[INFO] Installing {req['display_name']} via winget..."
        cmd = ["winget", "install", "--id", winget_id,
               "--silent", "--accept-package-agreements", "--accept-source-agreements"]
        exit_code = yield from self._stream_cmd(cmd)

        if exit_code == 0:
            yield f"[OK] {req['display_name']} installed."
            for hint in req.get("path_hints", []):
                if Path(hint).exists():
                    self._add_to_path(hint)
                    yield f"[OK] Added to PATH: {hint}"
                    break
        else:
            yield f"[WARN] winget exited with code {exit_code}."
            yield f"[INFO] Download manually: {req.get('fallback_url', '')}"
            self._open_url(req.get("fallback_url", ""))

    def _install_git(self, req: dict) -> Generator[str, None, None]:
        """Install Git for Windows — winget first, then GitHub Releases direct download."""
        yield "[INFO] Installing Git for Windows..."

        # ── Attempt 1: winget ─────────────────────────────────────────
        if self._winget_available():
            yield "[INFO] Trying winget (Git.Git)..."
            exit_code = yield from self._stream_cmd([
                "winget", "install", "--id", "Git.Git",
                "--silent", "--accept-package-agreements", "--accept-source-agreements",
            ])
            if exit_code == 0:
                yield "[OK] Git installed via winget."
                self._add_to_path(r"C:\Program Files\Git\cmd")
                os.environ["PATH"] = os.environ.get("PATH", "") + r";C:\Program Files\Git\cmd"
                yield "[OK] Git added to PATH."
                return
            yield "[WARN] winget failed — trying direct download from GitHub..."
        else:
            yield "[WARN] winget not available — trying direct download from GitHub..."

        # ── Attempt 2: GitHub Releases API ───────────────────────────
        try:
            import requests
        except ImportError:
            yield "[ERROR] 'requests' package not available. Run: pip install requests"
            self._open_url("https://git-scm.com/download/win")
            return

        yield "[INFO] Fetching latest Git for Windows release from GitHub API..."
        try:
            resp = requests.get(
                "https://api.github.com/repos/git-for-windows/git/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            asset = next(
                (a for a in data.get("assets", [])
                 if a["name"].endswith("-64-bit.exe") and "Git-" in a["name"]),
                None,
            )
            if not asset:
                raise ValueError("64-bit installer not found in release assets")

            version = data.get("tag_name", "latest")
            dl_url = asset["browser_download_url"]
            size_mb = asset["size"] // 1048576
            yield f"[INFO] Found Git {version} — {asset['name']} ({size_mb} MB)"
        except Exception as e:
            yield f"[ERROR] Could not fetch release info: {e}"
            yield "[INFO] Download Git manually from https://git-scm.com/download/win"
            self._open_url("https://git-scm.com/download/win")
            return

        tmp_path = Path(tempfile.gettempdir()) / asset["name"]
        yield f"[INFO] Downloading {asset['name']}..."
        try:
            r2 = requests.get(dl_url, stream=True, timeout=180)
            r2.raise_for_status()
            total = asset["size"]
            downloaded = 0
            last_pct = -1
            with open(tmp_path, "wb") as f:
                for chunk in r2.iter_content(chunk_size=131072):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded * 100 / total)
                        if pct != last_pct and pct % 10 == 0:
                            yield f"[DOWNLOAD] {pct}%  ({downloaded // 1048576} MB / {size_mb} MB)"
                            last_pct = pct
            yield "[OK] Download complete."
        except Exception as e:
            yield f"[ERROR] Download failed: {e}"
            self._open_url("https://git-scm.com/download/win")
            return

        yield "[INFO] Installing Git (silent, all users)..."
        exit_code = yield from self._stream_cmd([
            str(tmp_path),
            "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-",
            "/COMPONENTS=icons,ext\\reg\\shellhere,assoc,assoc_sh",
        ])
        if exit_code == 0:
            yield "[OK] Git installed."
            self._add_to_path(r"C:\Program Files\Git\cmd")
            os.environ["PATH"] = os.environ.get("PATH", "") + r";C:\Program Files\Git\cmd"
            yield "[OK] Git added to PATH. Re-check Prerequisites to confirm."
        else:
            yield f"[WARN] Installer exited with code {exit_code}."
            yield "[INFO] Try running the installer manually if Git is not detected."

    def _install_cmake(self, req: dict) -> Generator[str, None, None]:
        """Install CMake — winget first, then GitHub Releases MSI direct download."""
        yield "[INFO] Installing CMake..."

        # ── Attempt 1: winget ─────────────────────────────────────────
        if self._winget_available():
            yield "[INFO] Trying winget (Kitware.CMake)..."
            exit_code = yield from self._stream_cmd([
                "winget", "install", "--id", "Kitware.CMake",
                "--silent", "--accept-package-agreements", "--accept-source-agreements",
            ])
            if exit_code == 0:
                yield "[OK] CMake installed via winget."
                self._add_to_path(r"C:\Program Files\CMake\bin")
                os.environ["PATH"] = os.environ.get("PATH", "") + r";C:\Program Files\CMake\bin"
                yield "[OK] CMake added to PATH."
                return
            yield "[WARN] winget failed — trying direct download from GitHub..."
        else:
            yield "[WARN] winget not available — trying direct download from GitHub..."

        # ── Attempt 2: GitHub Releases API ───────────────────────────
        try:
            import requests
        except ImportError:
            yield "[ERROR] 'requests' package not available. Run: pip install requests"
            self._open_url("https://cmake.org/download/")
            return

        yield "[INFO] Fetching latest CMake release from GitHub API..."
        try:
            resp = requests.get(
                "https://api.github.com/repos/Kitware/CMake/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            # Prefer the .msi installer (silent-install friendly); fall back to .exe
            asset = next(
                (a for a in data.get("assets", [])
                 if "windows-x86_64.msi" in a["name"]),
                None,
            ) or next(
                (a for a in data.get("assets", [])
                 if "windows-x86_64.exe" in a["name"] and "rc" not in a["name"].lower()),
                None,
            )
            if not asset:
                raise ValueError("Windows x86_64 installer not found in release assets")

            version = data.get("tag_name", "latest")
            dl_url = asset["browser_download_url"]
            size_mb = asset["size"] // 1048576
            yield f"[INFO] Found CMake {version} — {asset['name']} ({size_mb} MB)"
        except Exception as e:
            yield f"[ERROR] Could not fetch release info: {e}"
            yield "[INFO] Download CMake manually from https://cmake.org/download/"
            self._open_url("https://cmake.org/download/")
            return

        tmp_path = Path(tempfile.gettempdir()) / asset["name"]
        yield f"[INFO] Downloading {asset['name']}..."
        try:
            r2 = requests.get(dl_url, stream=True, timeout=180)
            r2.raise_for_status()
            total = asset["size"]
            downloaded = 0
            last_pct = -1
            with open(tmp_path, "wb") as f:
                for chunk in r2.iter_content(chunk_size=131072):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded * 100 / total)
                        if pct != last_pct and pct % 10 == 0:
                            yield f"[DOWNLOAD] {pct}%  ({downloaded // 1048576} MB / {size_mb} MB)"
                            last_pct = pct
            yield "[OK] Download complete."
        except Exception as e:
            yield f"[ERROR] Download failed: {e}"
            self._open_url("https://cmake.org/download/")
            return

        yield "[INFO] Installing CMake (silent, system-wide)..."
        if asset["name"].endswith(".msi"):
            # MSI: /quiet /norestart, ADD_CMAKE_TO_PATH=System writes registry PATH entry
            exit_code = yield from self._stream_cmd([
                "msiexec", "/i", str(tmp_path),
                "/quiet", "/norestart",
                "ALLUSERS=1", "ADD_CMAKE_TO_PATH=System",
            ])
        else:
            exit_code = yield from self._stream_cmd([
                str(tmp_path), "/S", "--prefix=C:\\Program Files\\CMake",
            ])

        if exit_code == 0:
            yield "[OK] CMake installed."
            self._add_to_path(r"C:\Program Files\CMake\bin")
            os.environ["PATH"] = os.environ.get("PATH", "") + r";C:\Program Files\CMake\bin"
            yield "[OK] CMake added to PATH. Re-check Prerequisites to confirm."
        else:
            yield f"[WARN] Installer exited with code {exit_code}."
            yield "[INFO] CMake may still be installed — re-check Prerequisites."

    def _install_vs_cpp(self, req: dict, winget_id: str) -> Generator[str, None, None]:
        """Install or repair VS 2022 with the C++ Desktop Development workload."""
        vswhere = self._find_vswhere()

        # If VS is already installed, use the VS installer to add/repair the C++ workload
        if vswhere:
            install_path = self._vswhere_query(
                vswhere, ["-latest", "-property", "installationPath"]
            )
            vs_installer = Path(
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                "Microsoft Visual Studio", "Installer", "vs_installer.exe"
            )
            if install_path and vs_installer.exists():
                yield "[INFO] Visual Studio is installed but missing C++ workload."
                yield "[INFO] Running VS Installer to add 'Desktop development with C++'..."
                yield "[INFO] A UAC prompt and the VS Installer UI may appear."
                cmd = [
                    str(vs_installer), "modify",
                    "--installPath", install_path,
                    "--add", "Microsoft.VisualStudio.Workload.NativeDesktop",
                    "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                    "--add", "Microsoft.VisualStudio.Component.Windows11SDK.26100",
                    "--includeRecommended",
                    "--quiet", "--norestart",
                ]
                exit_code = yield from self._stream_cmd(cmd)
                if exit_code == 0:
                    yield "[OK] C++ workload added. Re-check Prerequisites to confirm."
                else:
                    yield f"[WARN] VS Installer exited with code {exit_code}."
                    yield "[INFO] You can also repair manually:"
                    yield "[INFO]  1. Open 'Visual Studio Installer'"
                    yield f"[INFO]  2. Click Modify next to your VS 2022 installation"
                    yield "[INFO]  3. Check 'Desktop development with C++'"
                    yield "[INFO]  4. Click Modify and wait for completion"
                return

        # VS not installed at all — install Build Tools via winget
        yield "[INFO] Installing Visual Studio 2022 Build Tools with C++ workload..."
        yield "[INFO] This is a large download (~2-4 GB). Please be patient."
        # winget can pass installer args via --override
        cpp_workload_args = (
            "--add Microsoft.VisualStudio.Workload.VCTools "
            "--add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 "
            "--add Microsoft.VisualStudio.Component.Windows11SDK.26100 "
            "--includeRecommended --quiet --norestart"
        )
        cmd = [
            "winget", "install", "--id", winget_id,
            "--accept-package-agreements", "--accept-source-agreements",
            "--override", cpp_workload_args,
        ]
        exit_code = yield from self._stream_cmd(cmd)
        if exit_code == 0:
            yield "[OK] VS Build Tools installed with C++ workload."
        else:
            yield f"[WARN] winget exited with code {exit_code}."
            yield "[INFO] Opening VS Build Tools download page..."
            self._open_url(req.get("fallback_url", ""))
            yield "[INFO] Download 'Build Tools for Visual Studio 2022', run it, and select:"
            yield "[INFO]   'Desktop development with C++'"

    def _check_mysql(self, req: dict) -> PrereqResult:
        """Detect MySQL by dynamically scanning the install tree, then running mysql --version."""
        name = req["display_name"]
        min_ver = req.get("min_version", "8.0.0")

        # Dynamically find the bin dir (works regardless of PATH)
        bin_dir = self._find_mysql_bin()
        if not bin_dir:
            return PrereqResult(req["id"], name, False, message="Not found in PATH")

        mysql_exe = str(Path(bin_dir) / "mysql.exe")
        try:
            result = subprocess.run(
                [mysql_exe, "--version"], capture_output=True, text=True, timeout=10
            )
            output = (result.stdout + result.stderr).strip()
            version = self._parse_version(output, req.get("version_regex", ""))
            ok = self._version_ok(version, min_ver)
            return PrereqResult(
                req["id"], name, ok,
                version=version,
                path=mysql_exe,
                message="" if ok else (
                    f"Found {version}, need {min_ver}+" if version else "Not found"
                ),
            )
        except Exception as e:
            return PrereqResult(req["id"], name, False, message=str(e))

    def _check_openssl(self, req: dict) -> PrereqResult:
        """Detect OpenSSL by scanning known install locations, then running openssl version."""
        name = req["display_name"]
        min_ver = req.get("min_version", "3.0.0")

        bin_dir = self._find_openssl_bin()
        if not bin_dir:
            return PrereqResult(req["id"], name, False, message="Not found in PATH")

        openssl_exe = str(Path(bin_dir) / "openssl.exe")
        try:
            result = subprocess.run(
                [openssl_exe, "version"], capture_output=True, text=True, timeout=10
            )
            output = (result.stdout + result.stderr).strip()
            version = self._parse_version(output, req.get("version_regex", ""))
            ok = self._version_ok(version, min_ver)
            return PrereqResult(
                req["id"], name, ok,
                version=version,
                path=openssl_exe,
                message="" if ok else (
                    f"Found {version}, need {min_ver}+" if version else "Not found"
                ),
            )
        except Exception as e:
            return PrereqResult(req["id"], name, False, message=str(e))

    def _install_mysql(self, req: dict) -> Generator[str, None, None]:
        """Install MySQL Server 8.x — winget with auto PATH detection."""
        yield "[INFO] Installing MySQL Server 8.x..."
        yield "[INFO] This requires administrator privileges. A UAC prompt may appear."

        if not self._winget_available():
            yield "[WARN] winget is not available on this system."
            yield "[INFO] Opening MySQL download page..."
            self._open_url(req.get("fallback_url", ""))
            yield "[INFO] Download 'MySQL Installer for Windows', run it, and choose:"
            yield "[INFO]   Server Only  →  set root password  →  Finish"
            yield "[INFO] Then re-check Prerequisites here."
            return

        cmd = ["winget", "install", "--id", "Oracle.MySQL",
               "--scope", "machine",
               "--accept-package-agreements", "--accept-source-agreements"]
        exit_code = yield from self._stream_cmd(cmd)

        if exit_code == 0:
            yield "[OK] MySQL installed via winget."
            mysql_bin = self._find_mysql_bin()
            if mysql_bin:
                yield f"[INFO] Detected MySQL at: {mysql_bin}"
                self._add_to_path(mysql_bin)
                os.environ["PATH"] = os.environ.get("PATH", "") + f";{mysql_bin}"
                yield "[OK] MySQL added to PATH."
            else:
                # MySQL may need a moment to finish setup — add the most likely path
                fallback_bin = r"C:\Program Files\MySQL\MySQL Server 8.0\bin"
                yield f"[INFO] MySQL bin not yet visible — pre-adding likely PATH: {fallback_bin}"
                self._add_to_path(fallback_bin)
            yield "[INFO] Restart Server Forge so the detection picks up the new PATH."
        else:
            yield "[WARN] winget install did not complete cleanly."
            yield "[INFO] Opening MySQL download page..."
            self._open_url(req["fallback_url"])
            yield f"[INFO]   {req['fallback_url']}"
            yield "[INFO] Download 'MySQL Installer for Windows', run it, and choose:"
            yield "[INFO]   Server Only  →  set root password  →  Finish"
            yield "[INFO] Then re-check Prerequisites here."

    def _install_openssl(self, req: dict) -> Generator[str, None, None]:
        """Install OpenSSL 3.x — winget first, then direct download from slproweb.com."""
        yield "[INFO] Installing OpenSSL 3.x (Shining Light Productions build)..."

        # ── Attempt 1: winget ─────────────────────────────────────────
        if self._winget_available():
            yield "[INFO] Trying winget (ShiningLight.OpenSSL)..."
            cmd = ["winget", "install", "--id", "ShiningLight.OpenSSL",
                   "--silent", "--accept-package-agreements", "--accept-source-agreements"]
            exit_code = yield from self._stream_cmd(cmd)

            if exit_code == 0:
                yield "[OK] OpenSSL installed via winget."
                openssl_bin = self._find_openssl_bin()
                if openssl_bin:
                    yield f"[INFO] Detected OpenSSL at: {openssl_bin}"
                    self._add_to_path(openssl_bin)
                    os.environ["PATH"] = os.environ.get("PATH", "") + f";{openssl_bin}"
                    yield "[OK] OpenSSL added to PATH."
                else:
                    # winget installs to Program Files — pre-add the standard path
                    fallback_bin = r"C:\Program Files\OpenSSL-Win64\bin"
                    self._add_to_path(fallback_bin)
                    os.environ["PATH"] = os.environ.get("PATH", "") + f";{fallback_bin}"
                    yield f"[INFO] Pre-added PATH: {fallback_bin}"
                return
            yield "[WARN] winget failed — downloading installer directly..."
        else:
            yield "[WARN] winget not available — downloading installer directly..."

        # ── Attempt 2: direct download from slproweb.com ─────────────
        yield from self._download_and_install_openssl(req)

    def _download_and_install_openssl(self, req: dict) -> Generator[str, None, None]:
        try:
            import requests
        except ImportError:
            yield "[ERROR] 'requests' package not available. Run: pip install requests"
            self._open_url(req["fallback_url"])
            return

        # Scrape slproweb.com to find the latest Win64 OpenSSL 3.x installer URL
        yield "[INFO] Fetching latest OpenSSL 3.x installer URL from slproweb.com..."
        installer_url = None
        try:
            resp = requests.get("https://slproweb.com/products/Win32OpenSSL.html", timeout=15)
            # Find Win64OpenSSL-3_x_x.exe (full installer, not Light)
            matches = re.findall(
                r'href="(/download/Win64OpenSSL-3[\d_]+\.exe)"', resp.text
            )
            if matches:
                installer_url = "https://slproweb.com" + matches[0]
                yield f"[INFO] Found: {installer_url}"
        except Exception as e:
            yield f"[WARN] Could not scrape installer URL: {e}"

        if not installer_url:
            yield "[INFO] Could not auto-detect installer. Opening download page..."
            self._open_url(req["fallback_url"])
            yield "[INFO] Download the Win64 OpenSSL (NOT Light) installer and run it."
            return

        # Download the installer
        yield "[INFO] Downloading OpenSSL installer (~50 MB)..."
        tmp_dir = Path(tempfile.gettempdir())
        installer_path = tmp_dir / "Win64OpenSSL_installer.exe"
        try:
            resp = requests.get(installer_url, stream=True, timeout=60)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(installer_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded * 100 / total)
                        yield f"[DOWNLOAD] {pct}%  ({downloaded // 1048576} MB / {total // 1048576} MB)"
            yield "[OK] Download complete."
        except Exception as e:
            yield f"[ERROR] Download failed: {e}"
            self._open_url(req["fallback_url"])
            return

        # Run installer silently
        yield "[INFO] Running OpenSSL installer (silent)..."
        install_dir = "C:\\OpenSSL-Win64"
        exit_code = yield from self._stream_cmd(
            [str(installer_path), "/silent", "/sp-", "/suppressmsgboxes",
             f"/DIR={install_dir}"]
        )
        if exit_code == 0:
            yield f"[OK] OpenSSL installed to {install_dir}"
            bin_dir = f"{install_dir}\\bin"
            yield f"[INFO] Adding {bin_dir} to PATH..."
            self._add_to_path(bin_dir)
            os.environ["PATH"] = os.environ.get("PATH", "") + f";{bin_dir}"
            yield "[OK] OpenSSL added to PATH. Re-check Prerequisites to confirm."
        else:
            yield f"[WARN] Installer exited with code {exit_code}."
            yield "[INFO] Try running the downloaded installer manually:"
            yield f"[INFO]   {installer_path}"

    def _install_boost(self, req: dict) -> Generator[str, None, None]:
        """Download pre-built Boost 1.86 MSVC binaries and install silently."""
        install_dir = Path(req.get("install_dir", r"C:\local\boost_1_86_0"))
        env_key = req.get("env_key", "BOOST_ROOT")
        installer_name = install_dir.name + "-msvc-14.3-64.exe"

        # Check if already present at the target (re-run after a failed install)
        version_hpp = install_dir / "boost" / "version.hpp"
        if version_hpp.exists():
            yield f"[OK] Boost already present at {install_dir}."
            yield f"[INFO] Setting {env_key} and updating PATH..."
            self._set_system_env(env_key, str(install_dir))
            self._add_to_path(str(install_dir))
            yield f"[OK] {env_key} = {install_dir}"
            return

        try:
            import requests
        except ImportError:
            yield "[ERROR] 'requests' package not available. Run: pip install requests"
            self._open_url(req["fallback_url"])
            return

        # ── Download: Artifactory (primary) → SourceForge (fallback) ─
        primary_url = req.get(
            "download_url",
            "https://boostorg.jfrog.io/artifactory/main/release/1.86.0/binaries/"
            "boost_1_86_0-msvc-14.3-64.exe"
        )
        fallback_url = req.get(
            "download_url_fallback",
            "https://sourceforge.net/projects/boost/files/boost-binaries/1.86.0/"
            "boost_1_86_0-msvc-14.3-64.exe/download"
        )

        tmp_dir = Path(tempfile.gettempdir())
        installer_path = tmp_dir / installer_name

        yield "[INFO] Downloading Boost 1.86.0 pre-built MSVC binaries (~700 MB)..."
        yield "[INFO] This may take several minutes depending on your connection."

        downloaded_ok = False
        for attempt, (url, label) in enumerate([
            (primary_url, "Boost Artifactory (official CDN)"),
            (fallback_url, "SourceForge mirror"),
        ], start=1):
            yield f"[INFO] Attempt {attempt}/2 — {label}"
            yield f"[INFO] {url}"
            try:
                session = requests.Session()
                session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                resp = session.get(url, stream=True, timeout=180, allow_redirects=True)
                resp.raise_for_status()

                # Reject HTML responses (SourceForge countdown page)
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type:
                    yield f"[WARN] Server returned HTML instead of binary — skipping."
                    continue

                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                last_pct = -1
                with open(installer_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=131072):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = int(downloaded * 100 / total)
                            if pct != last_pct and pct % 5 == 0:
                                yield (f"[DOWNLOAD] {pct}%  "
                                       f"({downloaded // 1048576} MB / {total // 1048576} MB)")
                                last_pct = pct

                # Sanity-check: NSIS installers start with "MZ" or "NullsoftInst"
                if installer_path.stat().st_size < 1_000_000:
                    yield f"[WARN] Downloaded file is too small ({installer_path.stat().st_size} bytes) — likely not a valid installer."
                    installer_path.unlink(missing_ok=True)
                    continue

                yield f"[OK] Download complete ({installer_path.stat().st_size // 1048576} MB)"
                downloaded_ok = True
                break
            except Exception as e:
                yield f"[WARN] Download failed: {e}"

        if not downloaded_ok:
            yield "[ERROR] All download attempts failed."
            yield "[INFO] Please download Boost manually from:"
            yield "[INFO]   https://sourceforge.net/projects/boost/files/boost-binaries/1.86.0/"
            yield "[INFO] Install the MSVC 14.3 x64 package, then re-check Prerequisites."
            self._open_url("https://sourceforge.net/projects/boost/files/boost-binaries/1.86.0/")
            return

        # ── Run NSIS installer silently ───────────────────────────────
        install_dir.parent.mkdir(parents=True, exist_ok=True)
        yield f"[INFO] Installing to {install_dir} (silent)..."
        # NSIS: /S = silent, /D=<path> = destination (no space allowed before path)
        exit_code = yield from self._stream_cmd(
            [str(installer_path), "/S", f"/D={install_dir}"]
        )

        if exit_code != 0:
            yield f"[WARN] Installer returned exit code {exit_code}."
            yield "[INFO] Checking if Boost files are present anyway..."

        # Verify headers exist
        if not (install_dir / "boost" / "version.hpp").exists():
            yield f"[ERROR] boost/version.hpp not found at {install_dir}."
            yield "[INFO] The installer may have failed. Try running it manually:"
            yield f"[INFO]   {installer_path}"
            return

        yield f"[OK] Boost installed at {install_dir}"

        # ── Set BOOST_ROOT + add root to system PATH ──────────────────
        yield f"[INFO] Setting {env_key} = {install_dir} ..."
        self._set_system_env(env_key, str(install_dir))
        yield f"[INFO] Adding {install_dir} to system PATH..."
        self._add_to_path(str(install_dir))
        yield f"[OK] Done. Re-check Prerequisites to confirm, then proceed to Compile."

    # ── Helpers ───────────────────────────────────────────────────────

    def _winget_available(self) -> bool:
        """Return True if winget is present and responsive."""
        try:
            r = subprocess.run(["winget", "--version"], capture_output=True, timeout=8)
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _find_openssl_bin(self) -> str:
        """Return the OpenSSL bin directory path after install, or ''."""
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates = [
            os.path.join(program_files, "OpenSSL-Win64", "bin"),
            os.path.join(program_files, "OpenSSL", "bin"),
            r"C:\OpenSSL-Win64\bin",
            r"C:\OpenSSL\bin",
        ]
        for candidate in candidates:
            if Path(candidate, "openssl.exe").exists():
                return candidate
        return ""

    def _find_mysql_bin(self) -> str:
        """Scan the standard MySQL install tree and return the bin directory path, or ''."""
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        mysql_root = Path(program_files) / "MySQL"
        if mysql_root.exists():
            # e.g. MySQL Server 8.0, MySQL Server 8.4 — pick the highest version
            candidates = sorted(mysql_root.glob("MySQL Server *"), reverse=True)
            for candidate in candidates:
                bin_dir = candidate / "bin"
                if (bin_dir / "mysqld.exe").exists() or (bin_dir / "mysql.exe").exists():
                    return str(bin_dir)
        return ""

    def _env_with_hints(self, req: dict) -> dict:
        """Return os.environ copy augmented with all path hints for this requirement."""
        env = os.environ.copy()
        hints = req.get("path_hints", [])
        if not hints and req.get("path_hint"):
            hints = [req["path_hint"]]
        existing = env.get("PATH", "")
        additions = ";".join(h for h in hints if Path(h).exists())
        if additions:
            env["PATH"] = additions + ";" + existing
        return env

    def _parse_version(self, output: str, pattern: str) -> str:
        if not pattern:
            return ""
        m = re.search(pattern, output)
        return m.group(1) if m else ""

    def _version_ok(self, version: str, min_ver: str) -> bool:
        if not version:
            return False
        try:
            return Version(version) >= Version(min_ver)
        except Exception:
            return bool(version)

    def _stream_cmd(self, cmd: list[str]) -> Generator[str, None, int]:
        """Stream a subprocess, yielding log lines. The generator's return value is the exit code.

        Usage inside another generator:
            exit_code = yield from self._stream_cmd(cmd)
        """
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace"
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    yield f"  {line}"
            proc.wait()
            return proc.returncode
        except FileNotFoundError:
            yield f"[ERROR] Command not found: {cmd[0]}"
            return 1
        except Exception as e:
            yield f"[ERROR] {e}"
            return 1

    def _set_system_env(self, key: str, value: str) -> None:
        """Persist a system-wide environment variable via the registry and setx."""
        try:
            subprocess.run(
                ["setx", key, value, "/M"],
                capture_output=True, timeout=10
            )
            # Also set for current process so immediate re-check works
            os.environ[key] = value
        except Exception as e:
            self._log.warning(f"Could not set env var {key}: {e}")

    def _add_to_path(self, directory: str) -> None:
        """Append a directory to the system PATH via registry + setx."""
        if winreg is None:
            self._log.warning("winreg not available — PATH update skipped")
            return
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0, winreg.KEY_READ | winreg.KEY_WRITE
            ) as key:
                current, _ = winreg.QueryValueEx(key, "Path")
                if directory.lower() not in current.lower():
                    new_path = current.rstrip(";") + ";" + directory
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                    os.environ["PATH"] = os.environ.get("PATH", "") + ";" + directory
        except Exception as e:
            self._log.warning(f"Could not update PATH: {e}")

    def _open_url(self, url: str) -> None:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
