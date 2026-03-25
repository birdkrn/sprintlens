"""SQLite3 기반 저장소 공통 베이스 모듈."""

from __future__ import annotations

import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)

_SQLITE_TIMEOUT = 10.0


class BaseStore(ABC):
    """SQLite3 기반 저장소의 공통 베이스 클래스.

    스레드 안전한 DB 접근, 테이블 자동 생성, timeout 설정을 제공한다.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @abstractmethod
    def _schema_sql(self) -> str:
        """테이블 생성 SQL을 반환한다."""

    def _init_db(self) -> None:
        """테이블을 생성한다."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(self._schema_sql())

    def _connect(self) -> sqlite3.Connection:
        """SQLite 연결을 생성한다."""
        return sqlite3.connect(str(self._db_path), timeout=_SQLITE_TIMEOUT)
