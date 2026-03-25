"""수동 매칭 오버라이드 저장소 모듈."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sprintlens.base_store import BaseStore
from sprintlens.logging_config import get_logger

logger = get_logger(__name__)

KST = timezone(timedelta(hours=9))


class ManualMatchStore(BaseStore):
    """수동 매칭 오버라이드를 저장하는 SQLite 저장소.

    사용자가 UI에서 이슈를 다른 작업으로 이동하면
    (page_id, issue_key) → (target_category, target_task) 매핑을 저장한다.
    AI 재매칭과 독립적으로 관리되어 재매칭 시에도 유지된다.
    """

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        logger.info("ManualMatchStore 초기화 완료 (DB: %s)", db_path)

    def _schema_sql(self) -> str:
        return """
            CREATE TABLE IF NOT EXISTS manual_matches (
                page_id TEXT NOT NULL,
                issue_key TEXT NOT NULL,
                target_category TEXT NOT NULL,
                target_task TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (page_id, issue_key)
            )
        """

    def get_overrides(self, page_id: str) -> dict[str, tuple[str, str]]:
        """해당 페이지의 수동 오버라이드를 반환한다.

        Returns:
            {issue_key: (target_category, target_task)} 딕셔너리.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT issue_key, target_category, target_task "
                "FROM manual_matches WHERE page_id = ?",
                (page_id,),
            ).fetchall()
        return {row[0]: (row[1], row[2]) for row in rows}

    def set_override(
        self,
        page_id: str,
        issue_key: str,
        target_category: str,
        target_task: str,
    ) -> None:
        """수동 오버라이드를 저장한다."""
        now = datetime.now(KST)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO manual_matches
                    (page_id, issue_key, target_category, target_task, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (page_id, issue_key, target_category, target_task, now.isoformat()),
            )
        logger.info("수동 매칭 저장: %s → %s/%s", issue_key, target_category, target_task)

    def remove_override(self, page_id: str, issue_key: str) -> None:
        """수동 오버라이드를 삭제한다."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM manual_matches WHERE page_id = ? AND issue_key = ?",
                (page_id, issue_key),
            )
        logger.info("수동 매칭 삭제: %s", issue_key)

    def clear(self, page_id: str) -> None:
        """해당 페이지의 모든 수동 오버라이드를 삭제한다."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM manual_matches WHERE page_id = ?",
                (page_id,),
            )
        logger.info("수동 매칭 전체 삭제: page_id=%s", page_id)
