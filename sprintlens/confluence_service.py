"""Confluence API 연동 서비스 모듈."""

from dataclasses import dataclass

from atlassian import Confluence

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SprintSchedule:
    """컨플루언스에서 가져온 스프린트 일정 정보."""

    title: str
    content_html: str
    page_id: str


class ConfluenceService:
    """Confluence API 클라이언트."""

    def __init__(
        self, base_url: str, username: str, api_token: str
    ) -> None:
        self._confluence = Confluence(
            url=base_url, username=username, password=api_token
        )

    def get_sprint_schedule(self, page_id: str) -> SprintSchedule:
        """스프린트 일정 페이지 내용을 가져온다."""
        page = self._confluence.get_page_by_id(
            page_id, expand="body.storage"
        )
        return SprintSchedule(
            title=page["title"],
            content_html=page["body"]["storage"]["value"],
            page_id=page["id"],
        )
