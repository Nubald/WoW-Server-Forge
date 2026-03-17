"""MySQL/MariaDB manager — connect, create databases, import SQL files."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Generator

from services.event_bus import get_bus
from services.log_service import get_log


class DatabaseManager:
    """All database operations for setting up a WoW server database."""

    def __init__(self):
        self._bus = get_bus()
        self._log = get_log()
        self._conn = None
        self._params: dict = {}

    def test_connection(self, host: str, port: int, user: str, password: str) -> tuple[bool, str]:
        """Test MySQL connectivity. Returns (success, message)."""
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=host, port=port, user=user, password=password,
                connection_timeout=5
            )
            ver = conn.get_server_info()
            conn.close()
            return True, f"Connected — MySQL {ver}"
        except Exception as e:
            return False, str(e)

    def connect(self, host: str, port: int, user: str, password: str) -> bool:
        try:
            import mysql.connector
            self._conn = mysql.connector.connect(
                host=host, port=port, user=user, password=password
            )
            self._params = dict(host=host, port=port, user=user, password=password)
            return True
        except Exception as e:
            self._log.error(f"DB connect failed: {e}")
            return False

    def create_database(self, db_name: str) -> bool:
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO "
                f"'{self._params['user']}'@'localhost'"
            )
            cursor.execute("FLUSH PRIVILEGES")
            cursor.close()
            self._log.info(f"Database '{db_name}' created/verified")
            return True
        except Exception as e:
            self._log.error(f"Failed to create database '{db_name}': {e}")
            return False

    def create_user(self, username: str, password: str) -> bool:
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                f"CREATE USER IF NOT EXISTS '{username}'@'localhost' "
                f"IDENTIFIED BY '{password}'"
            )
            cursor.close()
            return True
        except Exception as e:
            self._log.error(f"Failed to create user '{username}': {e}")
            return False

    def import_sql_file(self, db_name: str, sql_path: Path,
                        label: str = "") -> Generator[str, None, None]:
        """Import a SQL file using the mysql CLI (handles large files well)."""
        tag = label or sql_path.name
        yield f"[DB] Importing {tag} → {db_name}"
        self._bus.emit("db.import_progress", {"file": tag, "status": "running"})

        # Find mysql binary
        mysql_cmd = self._find_mysql_cmd()
        if not mysql_cmd:
            yield "[ERROR] mysql CLI not found. Add MySQL bin to PATH."
            return

        cmd = [
            mysql_cmd,
            f"--host={self._params.get('host', '127.0.0.1')}",
            f"--port={self._params.get('port', 3306)}",
            f"--user={self._params.get('user', 'root')}",
            f"--password={self._params.get('password', '')}",
            db_name
        ]
        try:
            with open(sql_path, "r", encoding="utf-8", errors="replace") as sql_file:
                proc = subprocess.Popen(
                    cmd, stdin=sql_file,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, encoding="utf-8", errors="replace"
                )
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        yield f"  {line}"
                proc.wait()
                if proc.returncode == 0:
                    yield f"[OK] {tag} imported"
                    self._bus.emit("db.import_progress", {"file": tag, "status": "done"})
                else:
                    yield f"[ERROR] Import failed (exit {proc.returncode})"
                    self._bus.emit("db.import_progress", {"file": tag, "status": "error"})
        except Exception as e:
            yield f"[ERROR] {e}"

    def import_directory(self, db_name: str, sql_dir: Path) -> Generator[str, None, None]:
        """Import all .sql files in a directory, sorted by name."""
        files = sorted(sql_dir.glob("*.sql"))
        yield f"[DB] Importing {len(files)} files from {sql_dir.name}/"
        for f in files:
            yield from self.import_sql_file(db_name, f)

    def import_updates(self, db_name: str, source_dir: Path,
                       db_key: str) -> Generator[str, None, None]:
        """Apply incremental SQL update files in version order.

        Searches for sql/updates/<db_key>/ (TrinityCore layout) and also
        sql/updates/world/, sql/updates/auth/, sql/updates/characters/.
        Files are applied in sorted order so numerically-named patches run correctly.
        """
        # Common update directory patterns used by TrinityCore / AzerothCore
        candidate_dirs = [
            source_dir / "sql" / "updates" / db_key,
            source_dir / "sql" / "updates" / f"{db_key}_db",
            source_dir / "sql" / "old" / db_key,
        ]
        update_dir = next((d for d in candidate_dirs if d.exists()), None)

        if not update_dir:
            yield f"[INFO] No update directory found for {db_key} — skipping incremental updates"
            return

        files = sorted(update_dir.glob("*.sql"))
        if not files:
            yield f"[INFO] No update files found in {update_dir}"
            return

        yield f"[DB] Applying {len(files)} incremental updates for {db_key}..."
        for f in files:
            yield from self.import_sql_file(db_name, f)

    def register_realm(self, name: str, address: str, auth_db: str,
                       port: int = 8085, expansion: int = 2) -> tuple[bool, str]:
        """Insert or update the realmlist entry in the auth database.

        expansion: 0=Vanilla, 1=TBC, 2=WotLK
        """
        if not self._conn:
            return False, "Not connected to MySQL"
        try:
            cursor = self._conn.cursor()
            cursor.execute(f"USE `{auth_db}`")
            cursor.execute("""
                INSERT INTO realmlist (name, address, port, icon, flag, timezone, allowedSecurityLevel, gamebuild, expansion)
                VALUES (%s, %s, %s, 0, 0, 1, 0, 12340, %s)
                ON DUPLICATE KEY UPDATE address=%s, port=%s, expansion=%s
            """, (name, address, port, expansion, address, port, expansion))
            self._conn.commit()
            cursor.close()
            self._log.info(f"Realm '{name}' registered at {address}:{port}")
            return True, f"Realm '{name}' registered at {address}:{port}"
        except Exception as e:
            self._log.error(f"Failed to register realm: {e}")
            return False, str(e)

    def check_exists(self, db_name: str) -> bool:
        try:
            cursor = self._conn.cursor()
            cursor.execute("SHOW DATABASES LIKE %s", (db_name,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception:
            return False

    def get_table_count(self, db_name: str) -> int:
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
                (db_name,)
            )
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        except Exception:
            return 0

    def _find_mysql_cmd(self) -> str | None:
        import shutil
        candidates = [
            shutil.which("mysql"),
            r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
            r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
        ]
        for c in candidates:
            if c and Path(c).exists():
                return c
        return None

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
