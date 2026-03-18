"""Jira API 연동 서비스 모듈."""

from dataclasses import dataclass

from atlassian import Jira

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SprintInfo:
    """스프린트 정보."""

    id: int
    name: str
    state: str
    start_date: str | None = None
    end_date: str | None = None


@dataclass
class IssueInfo:
    """지라 이슈 정보."""

    key: str
    summary: str
    status: str
    assignee: str | None = None
    story_key: str | None = None
    story_summary: str | None = None
    issue_type: str = ""


class JiraService:
    """Jira API 클라이언트."""

    def __init__(
        self, base_url: str, username: str, api_token: str, board_id: str
    ) -> None:
        self._jira = Jira(url=base_url, username=username, password=api_token)
        self._board_id = board_id

    def get_active_sprint(self) -> SprintInfo | None:
        """현재 활성 스프린트를 반환한다."""
        sprints = self._jira.get_all_sprints_from_board(self._board_id)
        for sprint in sprints.get("values", []):
            if sprint.get("state") == "active":
                return SprintInfo(
                    id=sprint["id"],
                    name=sprint["name"],
                    state=sprint["state"],
                    start_date=sprint.get("startDate"),
                    end_date=sprint.get("endDate"),
                )
        logger.warning("활성 스프린트를 찾을 수 없습니다.")
        return None

    def get_sprint_issues(self, sprint_id: int) -> list[IssueInfo]:
        """스프린트에 포함된 이슈 목록을 반환한다."""
        issues = self._jira.get_sprint_issues(sprint_id, start=0, limit=200)
        result: list[IssueInfo] = []

        for issue in issues.get("issues", []):
            fields = issue["fields"]
            assignee = fields.get("assignee")
            parent = fields.get("parent")

            result.append(
                IssueInfo(
                    key=issue["key"],
                    summary=fields.get("summary", ""),
                    status=fields["status"]["name"],
                    assignee=assignee["displayName"] if assignee else None,
                    story_key=parent["key"] if parent else None,
                    story_summary=parent["fields"]["summary"] if parent else None,
                    issue_type=fields["issuetype"]["name"],
                )
            )
        logger.info("스프린트 이슈 %d건 조회 완료", len(result))
        return result
