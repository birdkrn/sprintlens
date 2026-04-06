"""SQLite3 기반 별표 이슈 저장소 모듈."""

from __future__ import annotations

from pathlib import Path

from sprintlens.base_store import BaseStore
from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


class StarredIssueStore(BaseStore):
    """별표 이슈 저장소.

    사용자가 별표 표시한 이슈 키를 관리한다.
    """

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        logger.info("StarredIssueStore 초기화 완료 (DB: %s)", db_path)

    def _schema_sql(self) -> str:
        return """
            CREATE TABLE IF NOT EXISTS starred_issues (
                issue_key TEXT PRIMARY KEY
            )
        """

    def get_all(self) -> set[str]:
        """별표된 모든 이슈 키를 반환한다."""
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT issue_key FROM starred_issues").fetchall()
        return {row[0] for row in rows}

    def toggle(self, issue_key: str) -> bool:
        """별표를 토글한다. 반환값은 토글 후 별표 상태."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM starred_issues WHERE issue_key = ?",
                (issue_key,),
            ).fetchone()
            if row:
                conn.execute(
                    "DELETE FROM starred_issues WHERE issue_key = ?",
                    (issue_key,),
                )
                logger.info("별표 해제: %s", issue_key)
                return False
            else:
                conn.execute(
                    "INSERT INTO starred_issues (issue_key) VALUES (?)",
                    (issue_key,),
                )
                logger.info("별표 추가: %s", issue_key)
                return True
