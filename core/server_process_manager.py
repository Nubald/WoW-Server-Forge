"""Manage authserver and worldserver as child processes."""
from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from services.event_bus import get_bus
from services.log_service import get_log


@dataclass
class ProcessInfo:
    server_type: str
    status: str = "stopped"     # stopped | starting | running | crashed
    pid: int = 0
    uptime_seconds: float = 0.0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    started_at: float = 0.0


class ServerProcessManager:
    """Spawn, monitor, and control authserver/worldserver processes."""

    def __init__(self):
        self._bus = get_bus()
        self._log = get_log()
        self._processes: dict[str, subprocess.Popen] = {}
        self._info: dict[str, ProcessInfo] = {
            "auth":  ProcessInfo("auth"),
            "world": ProcessInfo("world"),
        }
        self._stop_monitor = False
        self._monitor_thread: threading.Thread | None = None
        self._output_threads: dict[str, threading.Thread] = {}

    def start(self, server_type: str, exe_path: Path, working_dir: Path) -> bool:
        if server_type in self._processes:
            proc = self._processes[server_type]
            if proc.poll() is None:
                self._log.warning(f"{server_type} is already running (PID {proc.pid})")
                return False

        if not exe_path.exists():
            self._log.error(f"Executable not found: {exe_path}")
            self._bus.emit("process.status_changed",
                           {"server": server_type, "status": "error", "message": "EXE not found"})
            return False

        self._log.info(f"Starting {server_type}: {exe_path}")
        self._info[server_type].status = "starting"
        self._bus.emit("process.status_changed",
                       {"server": server_type, "status": "starting"})

        try:
            proc = subprocess.Popen(
                [str(exe_path)],
                cwd=str(working_dir),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True, bufsize=1,
                encoding="utf-8", errors="replace"
            )
            self._processes[server_type] = proc
            self._info[server_type].pid = proc.pid
            self._info[server_type].started_at = time.time()
            self._info[server_type].status = "running"

            # Stream output
            t = threading.Thread(
                target=self._read_output,
                args=(server_type, proc),
                daemon=True, name=f"output_{server_type}"
            )
            t.start()
            self._output_threads[server_type] = t

            self._ensure_monitor()
            self._bus.emit("process.status_changed",
                           {"server": server_type, "status": "running", "pid": proc.pid})
            return True
        except Exception as e:
            self._log.error(f"Failed to start {server_type}: {e}")
            self._info[server_type].status = "crashed"
            self._bus.emit("process.status_changed",
                           {"server": server_type, "status": "crashed", "message": str(e)})
            return False

    def stop(self, server_type: str, graceful: bool = True) -> None:
        proc = self._processes.get(server_type)
        if not proc:
            return
        self._log.info(f"Stopping {server_type}...")
        if graceful:
            self.send_command(server_type, "server shutdown 3")
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
        else:
            proc.terminate()
        self._info[server_type].status = "stopped"
        self._bus.emit("process.status_changed",
                       {"server": server_type, "status": "stopped"})

    def restart(self, server_type: str, exe_path: Path, working_dir: Path) -> None:
        self.stop(server_type)
        time.sleep(2)
        self.start(server_type, exe_path, working_dir)

    def send_command(self, server_type: str, command: str) -> bool:
        proc = self._processes.get(server_type)
        if proc and proc.stdin and proc.poll() is None:
            try:
                proc.stdin.write(command + "\n")
                proc.stdin.flush()
                return True
            except Exception:
                pass
        return False

    def get_info(self, server_type: str) -> ProcessInfo:
        return self._info.get(server_type, ProcessInfo(server_type))

    def _read_output(self, server_type: str, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._bus.emit("process.log_line",
                                   {"server": server_type, "line": line})
        except Exception:
            pass

    def _ensure_monitor(self) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_monitor = False
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="process_monitor"
        )
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._stop_monitor:
            for stype, proc in list(self._processes.items()):
                info = self._info[stype]
                if proc.poll() is not None and info.status == "running":
                    info.status = "crashed"
                    self._bus.emit("process.status_changed",
                                   {"server": stype, "status": "crashed"})
                elif proc.poll() is None:
                    info.uptime_seconds = time.time() - info.started_at
                    try:
                        import psutil
                        p = psutil.Process(proc.pid)
                        info.memory_mb = p.memory_info().rss / 1_048_576
                        info.cpu_percent = p.cpu_percent(interval=None)
                    except Exception:
                        pass
                    self._bus.emit("process.stats",
                                   {"server": stype,
                                    "uptime": info.uptime_seconds,
                                    "memory_mb": info.memory_mb,
                                    "cpu_percent": info.cpu_percent})
            time.sleep(2)
