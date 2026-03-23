"""SQLite3 기반 캐시 저장소 모듈."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)

KST = timezone(timedelta(hours=9))


class CacheStore:
    """SQLite3 기반 키-값 캐시 저장소.

    TTL(Time To Live) 기반으로 캐시를 관리한다.
    스레드 안전하게 동작한다.
    """

    def __init__(self, db_path: Path, ttl_minutes: int = 60) -> None:
        self._db_path = db_path
        self._ttl_minutes = ttl_minutes
        self._lock = threading.Lock()
        self._init_db()
        logger.info(
            "CacheStore 초기화 완료 (DB: %s, TTL: %d분)",
            db_path,
            ttl_minutes,
        )

    def _init_db(self) -> None:
        """캐시 테이블을 생성한다."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        """SQLite 연결을 생성한다."""
        return sqlite3.connect(str(self._db_path))

    def get(self, key: str) -> tuple[dict | list | None, datetime | None]:
        """캐시에서 값을 조회한다.

        TTL이 만료되지 않은 경우에만 값을 반환한다.

        Returns:
            (데이터, 업데이트시각) 튜플. 캐시 미스 시 (None, None).
        """
        with self._lock, self._connect() as conn:
                row = conn.execute(
                    "SELECT value, updated_at FROM cache WHERE key = ?",
                    (key,),
                ).fetchone()

        if not row:
            return None, None

        updated_at = datetime.fromisoformat(row[1])
        elapsed = datetime.now(KST) - updated_at

        if elapsed > timedelta(minutes=self._ttl_minutes):
            logger.info("캐시 만료: %s (%.0f분 경과)", key, elapsed.total_seconds() / 60)
            return None, None

        logger.info(
            "캐시 히트: %s (%.0f분 전 업데이트)",
            key,
            elapsed.total_seconds() / 60,
        )
        data = json.loads(row[0])
        return data, updated_at

    def set(self, key: str, value: dict | list) -> datetime:
        """캐시에 값을 저장한다.

        Returns:
            저장된 시각 (KST).
        """
        now = datetime.now(KST)
        serialized = json.dumps(value, ensure_ascii=False)

        with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache (key, value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, serialized, now.isoformat()),
                )

        logger.info("캐시 저장: %s (%d bytes)", key, len(serialized))
        return now

    def invalidate(self, key: str) -> None:
        """특정 키의 캐시를 삭제한다."""
        with self._lock, self._connect() as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        logger.info("캐시 삭제: %s", key)
