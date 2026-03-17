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
        """Return an environment that suppresses credential prompts for public repos.

        Git Credential Manager (GCM) on Windows intercepts all github.com HTTPS
        requests and can pop up a browser OAuth flow even for public repos.
        Setting credential.helper to empty string overrides GCM for this process.
        GIT_TERMINAL_PROMPT=0 blocks any fallback terminal prompt.
        GIT_ASKPASS=echo returns empty string to any password prompts.
        """
        import os
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "echo"
        return env

    def _run(self, cmd: list[str], cwd: Path | None = None) -> Generator[str, None, None]:
        """Run a command, yielding output lines and emitting them as log events.

        All git commands are run with credential prompts disabled so that
        public-repo clones/fetches never trigger a browser sign-in dialog.
        """
        # Prepend git config flags to disable credential helper for git commands
        full_cmd = cmd
        if cmd and cmd[0] == "git":
            full_cmd = ["git", "-c", "credential.helper=", "-c", "core.askpass="] + cmd[1:]

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
        yield f"[GIT] Adding submodule {url}"
        yield from self._run(
            ["git", "submodule", "add", "-b", branch, url, sub_path],
            cwd=repo_path
        )

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
