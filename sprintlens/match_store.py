"""AI 매칭 결과 영구 저장소 모듈."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sprintlens.base_store import BaseStore
from sprintlens.logging_config import get_logger

logger = get_logger(__name__)

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class SavedMatch:
    """저장된 매칭 결과."""

    page_id: str
    schedule_hash: str
    issues_hash: str
    match_data: list[dict]
    updated_at: datetime


class MatchStore(BaseStore):
    """AI 매칭 결과를 영구 저장하는 SQLite 저장소.

    매칭(task → issue keys 연결)은 스프린트 내에서 거의 변경되지 않으므로,
    결과를 DB에 저장하고 일정/이슈 목록이 변경될 때만 재매칭한다.
    """

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        logger.info("MatchStore 초기화 완료 (DB: %s)", db_path)

    def _schema_sql(self) -> str:
        return """
            CREATE TABLE IF NOT EXISTS matches (
                page_id TEXT PRIMARY KEY,
                schedule_hash TEXT NOT NULL,
                issues_hash TEXT NOT NULL,
                match_data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """

    def get(self, page_id: str) -> SavedMatch | None:
        """저장된 매칭 결과를 조회한다."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT page_id, schedule_hash, issues_hash, "
                "match_data, updated_at FROM matches WHERE page_id = ?",
                (page_id,),
            ).fetchone()

        if not row:
            return None

        return SavedMatch(
            page_id=row[0],
            schedule_hash=row[1],
            issues_hash=row[2],
            match_data=json.loads(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
        )

    def save(
        self,
        page_id: str,
        schedule_hash: str,
        issues_hash: str,
        match_data: list[dict],
    ) -> datetime:
        """매칭 결과를 저장한다.

        Returns:
            저장된 시각 (KST).
        """
        now = datetime.now(KST)
        serialized = json.dumps(match_data, ensure_ascii=False)

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO matches
                    (page_id, schedule_hash, issues_hash, match_data, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (page_id, schedule_hash, issues_hash, serialized, now.isoformat()),
            )

        logger.info("매칭 결과 저장: page_id=%s", page_id)
        return now

    def delete(self, page_id: str) -> None:
        """저장된 매칭 결과를 삭제한다."""
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM matches WHERE page_id = ?", (page_id,))
        logger.info("매칭 결과 삭제: page_id=%s", page_id)
