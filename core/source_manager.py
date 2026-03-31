"""Git source code management — clone, update, submodule operations."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Generator

from services.event_bus import get_bus
from services.log_service import get_log


class SourceManager:
    """Handles all git operations for server source code and modules."""

    def __init__(self):
        self._bus = get_bus()
        self._log = get_log()

    @staticmethod
    def _git_env() -> dict:
        """Return an environment that fully isolates git from any credential helpers.

        Windows Git Credential Manager (GCM) hooks at the system gitconfig level
        and injects stored tokens even when -c credential.helper= is passed.
        The only reliable fix is to run git with GIT_CONFIG_NOSYSTEM=1 and a
        clean temp HOME/USERPROFILE so no system or user gitconfig is loaded at
        all — meaning no credential helper, no stored token, anonymous access.
        A minimal .gitconfig is written to the temp dir to keep git happy.
        """
        import os
        import tempfile

        tmp = tempfile.mkdtemp(prefix="sgforge_git_")
        # Write a minimal gitconfig that explicitly disables credential helpers
        gitconfig_path = os.path.join(tmp, ".gitconfig")
        with open(gitconfig_path, "w") as f:
            f.write("[credential]\n\thelper =\n[core]\n\taskpass =\n")

        env = os.environ.copy()
        env["HOME"] = tmp
        env["USERPROFILE"] = tmp
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "echo"
        env["GCM_INTERACTIVE"] = "never"
        return env

    def _run(self, cmd: list[str], cwd: Path | None = None) -> Generator[str, None, None]:
        """Run a command, yielding output lines and emitting them as log events.

        All git commands run with a clean isolated environment — no system
        gitconfig, no credential helpers, anonymous access to public repos.
        """
        full_cmd = cmd

        try:
            proc = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(cwd) if cwd else None,
                encoding="utf-8", errors="replace",
                env=self._git_env()
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._bus.emit("build.log_line", line)
                    yield line
            proc.wait()
            if proc.returncode != 0:
                msg = f"[ERROR] Command failed (exit {proc.returncode}): {' '.join(cmd)}"
                self._bus.emit("build.log_line", msg)
                yield msg
        except FileNotFoundError:
            msg = f"[ERROR] Command not found: {cmd[0]}"
            self._bus.emit("build.log_line", msg)
            yield msg

    def clone(self, url: str, target: Path, branch: str = "master") -> Generator[str, None, None]:
        yield f"[GIT] Cloning {url} → {target}"
        self._bus.emit("build.log_line", f"Cloning repository: {url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["git", "clone", "--branch", branch, "--depth", "1",
               "--recurse-submodules", url, str(target)]
        yield from self._run(cmd)

    def update(self, repo_path: Path) -> Generator[str, None, None]:
        yield f"[GIT] Updating {repo_path.name}"
        self._bus.emit("build.log_line", f"Pulling latest changes for {repo_path.name}...")
        yield from self._run(["git", "pull", "--rebase"], cwd=repo_path)
        yield from self._run(
            ["git", "submodule", "update", "--init", "--recursive"], cwd=repo_path
        )

    def add_submodule(self, repo_path: Path, url: str, sub_path: str,
                      branch: str = "master") -> Generator[str, None, None]:
        """Add a module repo, falling back to ZIP download if git auth fails.

        Windows Credential Manager injects stored (invalid) GitHub tokens at the
        OS level, below git config — no env var or -c flag can suppress it.
        If git clone fails with an auth error we fall back to downloading the
        repo as a ZIP via Python's urllib (no git, no credentials involved).
        """
        yield f"[GIT] Adding submodule {url}"
        clone_target = repo_path / sub_path

        if not clone_target.exists():
            yield f"[GIT] Cloning {url} → {clone_target}"
            git_failed = False
            lines = list(self._run(
                ["git", "clone", "-b", branch, "--recurse-submodules", url,
                 str(clone_target)]
            ))
            for line in lines:
                yield line
            if any("Authentication failed" in l or "Invalid username" in l for l in lines):
                git_failed = True

            if git_failed or not clone_target.exists():
                yield "[WARN] git clone failed due to credential interference — using ZIP download fallback"
                yield from self._download_zip(url, branch, clone_target)
        else:
            yield f"[GIT] Target already exists, skipping clone: {clone_target}"

        if not clone_target.exists():
            yield f"[ERROR] Module directory not created — cannot register submodule"
            return

        # Register in .gitmodules
        gitmodules = repo_path / ".gitmodules"
        entry = f'\n[submodule "{sub_path}"]\n\tpath = {sub_path}\n\turl = {url}\n\tbranch = {branch}\n'
        existing = gitmodules.read_text(encoding="utf-8") if gitmodules.exists() else ""
        if f'path = {sub_path}' not in existing:
            with gitmodules.open("a", encoding="utf-8") as f:
                f.write(entry)
            yield f"[GIT] Registered {sub_path} in .gitmodules"

        yield from self._run(["git", "submodule", "init", sub_path], cwd=repo_path)
        yield from self._run(["git", "add", ".gitmodules", sub_path], cwd=repo_path)

    def _download_zip(self, url: str, branch: str, target: Path) -> Generator[str, None, None]:
        """Download a GitHub repo as a ZIP and extract it to target."""
        import re
        import urllib.request
        import zipfile
        import tempfile

        # Convert https://github.com/Owner/repo.git → Owner/repo
        m = re.match(r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?$", url)
        if not m:
            yield f"[ERROR] Cannot parse GitHub URL for ZIP fallback: {url}"
            return

        slug = m.group(1)
        zip_url = f"https://github.com/{slug}/archive/refs/heads/{branch}.zip"
        yield f"[INFO] Downloading {zip_url}"

        try:
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = Path(tmp) / "repo.zip"
                urllib.request.urlretrieve(zip_url, zip_path)
                yield f"[INFO] Extracting..."
                with zipfile.ZipFile(zip_path) as zf:
                    # ZIP root is <repo>-<branch>/ — strip it
                    prefix = zf.namelist()[0]
                    target.mkdir(parents=True, exist_ok=True)
                    for member in zf.namelist():
                        rel = member[len(prefix):]
                        if not rel:
                            continue
                        dest = target / rel
                        if member.endswith("/"):
                            dest.mkdir(parents=True, exist_ok=True)
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(zf.read(member))
            yield f"[OK] Module downloaded to {target}"
        except Exception as e:
            yield f"[ERROR] ZIP download failed: {e}"

    def get_commit(self, repo_path: Path) -> str:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, cwd=str(repo_path)
            )
            return r.stdout.strip()
        except Exception:
            return "unknown"

    def get_branch(self, repo_path: Path) -> str:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, cwd=str(repo_path)
            )
            return r.stdout.strip()
        except Exception:
            return "unknown"

    def is_repo(self, path: Path) -> bool:
        return (path / ".git").exists()

    def check_for_updates(self, repo_path: Path) -> bool:
        """Return True if remote has commits ahead of local."""
        try:
            subprocess.run(["git", "fetch", "--dry-run"], cwd=str(repo_path),
                           capture_output=True, timeout=15)
            r = subprocess.run(
                ["git", "rev-list", "HEAD..@{u}", "--count"],
                capture_output=True, text=True, cwd=str(repo_path)
            )
            count = int(r.stdout.strip() or "0")
            return count > 0
        except Exception:
            return False
