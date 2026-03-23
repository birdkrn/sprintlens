"""SQLite3 기반 설정 저장소 모듈."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


class SettingsStore:
    """SQLite3 기반 키-값 설정 저장소.

    웹 UI에서 변경 가능한 설정을 관리한다.
    스레드 안전하게 동작한다.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        logger.info("SettingsStore 초기화 완료 (DB: %s)", db_path)

    def _init_db(self) -> None:
        """설정 테이블을 생성한다."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        """SQLite 연결을 생성한다."""
        return sqlite3.connect(str(self._db_path))

    def get(self, key: str, default: str = "") -> str:
        """설정값을 조회한다."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else default

    def get_all(self) -> dict[str, str]:
        """모든 설정을 딕셔너리로 반환한다."""
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return dict(rows)

    def set(self, key: str, value: str) -> None:
        """설정값을 저장한다."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        logger.info("설정 저장: %s", key)

    def set_many(self, items: dict[str, str]) -> None:
        """여러 설정을 한번에 저장한다."""
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                items.items(),
            )
        logger.info("설정 %d건 저장", len(items))
