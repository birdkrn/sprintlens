"""Confluence API 연동 서비스 모듈."""

from dataclasses import dataclass

from atlassian import Confluence

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PageInfo:
    """Confluence 페이지 정보."""

    page_id: str
    title: str
    body_html: str
    version: int = 0


class ConfluenceService:
    """Confluence API 클라이언트.

    사내 온프레미스 Confluence Server v7.4.3에 Basic Auth로 접속한다.
    """

    def __init__(
        self, base_url: str, username: str, password: str
    ) -> None:
        self._confluence = Confluence(
            url=base_url, username=username, password=password
        )
        logger.info("ConfluenceService 초기화 완료")

    def get_page(self, page_id: str) -> PageInfo:
        """페이지 ID로 콘텐츠를 조회한다."""
        page = self._confluence.get_page_by_id(
            page_id, expand="body.storage,version"
        )
        result = PageInfo(
            page_id=page["id"],
            title=page["title"],
            body_html=page["body"]["storage"]["value"],
            version=page.get("version", {}).get("number", 0),
        )
        logger.info("페이지 조회 완료: %s (ID: %s)", result.title, page_id)
        return result
