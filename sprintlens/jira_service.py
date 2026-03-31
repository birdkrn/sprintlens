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
    goal: str = ""


@dataclass
class IssueInfo:
    """지라 이슈 정보."""

    key: str
    summary: str
    status: str
    status_category: str = ""  # "done", "indeterminate", "new"
    assignee: str | None = None
    story_key: str | None = None
    story_summary: str | None = None
    issue_type: str = ""
    icon_url: str = ""
    parent_key: str = ""
    parent_summary: str = ""
    resolved_date: str | None = None  # "YYYY-MM-DD" (done 상태 전환 날짜)


@dataclass
class ProjectInfo:
    """지라 프로젝트 정보."""

    key: str
    name: str
    description: str = ""
    lead: str = ""


class JiraService:
    """Jira API 클라이언트.

    사내 온프레미스 Jira Server v8.5.7에 Basic Auth로 접속한다.
    atlassian-python-api의 Jira 객체를 래핑하여 프로젝트에 필요한 기능을 제공한다.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        board_id: str = "",
    ) -> None:
        self._jira = Jira(url=base_url, username=username, password=password)
        self._board_id = board_id
        logger.info("JiraService 초기화 완료 (보드 ID: %s)", board_id or "없음")

    # ------------------------------------------------------------------
    # 프로젝트
    # ------------------------------------------------------------------

    def get_project_info(self, project_key: str) -> ProjectInfo:
        """프로젝트 기본 정보를 조회한다."""
        data = self._jira.project(project_key)
        lead = data.get("lead", {})
        return ProjectInfo(
            key=data["key"],
            name=data["name"],
            description=data.get("description", ""),
            lead=lead.get("displayName", ""),
        )

    # ------------------------------------------------------------------
    # 스프린트
    # ------------------------------------------------------------------

    def get_active_sprint(self) -> SprintInfo | None:
        """현재 활성 스프린트를 반환한다."""
        sprints = self.get_board_sprints(state="active")
        if sprints:
            return sprints[0]
        logger.warning("활성 스프린트를 찾을 수 없습니다.")
        return None

    def get_board_sprints(self, state: str | None = None) -> list[SprintInfo]:
        """보드의 스프린트 목록을 반환한다.

        Args:
            state: 필터링할 상태 ("active", "closed", "future"). None이면 전체 반환.
        """
        params: dict[str, str] = {}
        if state:
            params["state"] = state

        data = self._jira.get_all_sprints_from_board(
            self._board_id, **params
        )
        sprints: list[SprintInfo] = []
        for s in data.get("values", []):
            sprints.append(
                SprintInfo(
                    id=s["id"],
                    name=s["name"],
                    state=s["state"],
                    start_date=s.get("startDate"),
                    end_date=s.get("endDate"),
                    goal=s.get("goal", ""),
                )
            )
        logger.info(
            "스프린트 %d건 조회 (state=%s)", len(sprints), state or "all"
        )
        return sprints

    # ------------------------------------------------------------------
    # 이슈
    # ------------------------------------------------------------------

    def get_sprint_issues(
        self, sprint_id: int, *, expand_changelog: bool = False
    ) -> list[IssueInfo]:
        """스프린트에 포함된 이슈 목록을 반환한다 (전체 페이지네이션).

        Args:
            sprint_id: 스프린트 ID.
            expand_changelog: True이면 changelog를 포함하여 resolved_date를 추출한다.
        """
        all_issues: list[dict] = []
        start_at = 0
        page_size = 200

        while True:
            params = f"startAt={start_at}&maxResults={page_size}"
            if expand_changelog:
                params += "&expand=changelog"
            url = (
                f"rest/agile/1.0/sprint/{sprint_id}/issue?{params}"
            )
            data = self._jira.get(url)
            issues = data.get("issues", [])
            all_issues.extend(issues)

            total = data.get("total", 0)
            if len(all_issues) >= total or not issues:
                break
            start_at = len(all_issues)

        result = self._parse_issues(all_issues)
        logger.info("스프린트 이슈 %d건 조회 완료", len(result))
        return result

    def get_issue_detail(self, issue_key: str) -> IssueInfo:
        """단일 이슈 상세 정보를 조회한다."""
        issue = self._jira.issue(issue_key)
        return self._parse_issue(issue)

    def search_issues(
        self, jql: str, max_results: int = 200
    ) -> list[IssueInfo]:
        """JQL로 이슈를 검색한다.

        Args:
            jql: JQL 쿼리 문자열.
            max_results: 최대 결과 수.
        """
        all_issues: list[dict] = []
        start_at = 0

        while True:
            data = self._jira.jql(
                jql, start=start_at, limit=min(100, max_results - start_at)
            )
            issues = data.get("issues", [])
            all_issues.extend(issues)

            if len(all_issues) >= data.get("total", 0):
                break
            if len(all_issues) >= max_results:
                break
            start_at = len(all_issues)

        result = self._parse_issues(all_issues)
        logger.info("JQL 검색 결과 %d건 (쿼리: %s)", len(result), jql)
        return result

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _parse_issues(self, issues: list[dict]) -> list[IssueInfo]:
        """이슈 목록을 IssueInfo 리스트로 변환한다.

        파싱 실패한 이슈는 건너뛴다.
        """
        result: list[IssueInfo] = []
        for issue in issues:
            parsed = self._parse_issue(issue)
            if parsed:
                result.append(parsed)
        return result

    @staticmethod
    def _parse_issue(issue: dict) -> IssueInfo | None:
        """단일 이슈 딕셔너리를 IssueInfo로 변환한다.

        필수 필드가 누락되면 None을 반환한다.
        """
        try:
            fields = issue.get("fields")
            if not fields:
                logger.warning("이슈 필드 누락: %s", issue.get("key"))
                return None

            status = fields.get("status") or {}
            issuetype = fields.get("issuetype") or {}
            assignee = fields.get("assignee")
            parent = fields.get("parent")
            status_category = (
                status.get("statusCategory", {}).get("key", "")
            )

            resolved_date = _extract_resolved_date(issue)

            return IssueInfo(
                key=issue.get("key", ""),
                summary=fields.get("summary", ""),
                status=status.get("name", ""),
                status_category=status_category,
                assignee=assignee["displayName"] if assignee else None,
                story_key=parent["key"] if parent else None,
                story_summary=(
                    parent["fields"]["summary"] if parent else None
                ),
                issue_type=issuetype.get("name", ""),
                icon_url=issuetype.get("iconUrl", ""),
                parent_key=parent["key"] if parent else "",
                parent_summary=(
                    parent["fields"]["summary"] if parent else ""
                ),
                resolved_date=resolved_date,
            )
        except (KeyError, TypeError) as e:
            logger.warning("이슈 파싱 실패 %s: %s", issue.get("key"), e)
            return None


def _extract_resolved_date(issue: dict) -> str | None:
    """현재 done 상태인 이슈의 마지막 상태 변경 날짜를 추출한다.

    현재 statusCategory가 done인 이슈에 대해서만,
    changelog에서 가장 마지막 상태 변경 날짜를 반환한다.

    Returns:
        "YYYY-MM-DD" 형식 문자열 또는 None.
    """
    # 현재 상태가 done이 아니면 None
    status = issue.get("fields", {}).get("status", {})
    status_category = status.get("statusCategory", {}).get("key", "")
    if status_category != "done":
        return None

    changelog = issue.get("changelog", {})
    histories = changelog.get("histories", [])
    if not histories:
        return None

    # 마지막 상태 변경 날짜 추출
    resolved_date = None
    for history in histories:
        for item in history.get("items", []):
            if item.get("field") == "status":
                resolved_date = history["created"][:10]

    return resolved_date
