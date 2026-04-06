"""스프린트 리포트 생성 서비스 모듈."""

from dataclasses import dataclass, field

from sprintlens.jira_service import IssueInfo, JiraService, SprintInfo
from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AssigneeReport:
    """개인별 일감 현황."""

    name: str
    issues: list[IssueInfo] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.issues)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.issues if i.status_category == "done")

    @property
    def in_progress_count(self) -> int:
        return sum(1 for i in self.issues if i.status_category == "indeterminate")

    @property
    def todo_count(self) -> int:
        return self.total - self.done_count - self.in_progress_count


@dataclass
class StoryReport:
    """스토리별 일감 현황."""

    story_key: str
    story_summary: str
    issues: list[IssueInfo] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.issues)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.issues if i.status_category == "done")


@dataclass
class SprintReport:
    """스프린트 전체 리포트."""

    sprint: SprintInfo
    issues: list[IssueInfo]
    by_assignee: list[AssigneeReport] = field(default_factory=list)
    by_story: list[StoryReport] = field(default_factory=list)
    by_dev_team: list[AssigneeReport] = field(default_factory=list)
    by_line_team: list[AssigneeReport] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.issues if i.status_category == "done")

    @property
    def in_progress_count(self) -> int:
        return sum(1 for i in self.issues if i.status_category == "indeterminate")

    @property
    def progress_percent(self) -> float:
        if self.total_issues == 0:
            return 0.0
        return (self.done_count / self.total_issues) * 100

    @property
    def dev_issues(self) -> list[IssueInfo]:
        """개발팀 이슈 flat 리스트 (변경일 내림차순)."""
        issues = [i for ar in self.by_dev_team for i in ar.issues]
        return sorted(issues, key=lambda i: i.updated, reverse=True)

    @property
    def line_issues(self) -> list[IssueInfo]:
        """라인 이슈 flat 리스트 (변경일 내림차순)."""
        issues = [i for ar in self.by_line_team for i in ar.issues]
        return sorted(issues, key=lambda i: i.updated, reverse=True)


class ReportService:
    """스프린트 리포트를 생성하는 서비스."""

    def __init__(self, jira_service: JiraService) -> None:
        self._jira = jira_service

    def generate_sprint_report(self) -> SprintReport | None:
        """현재 활성 스프린트의 리포트를 생성한다."""
        sprint = self._jira.get_active_sprint()
        if not sprint:
            return None

        issues = self._jira.get_sprint_issues(sprint.id)
        by_assignee = self._group_by_assignee(issues)
        by_story = self._group_by_story(issues)

        report = SprintReport(
            sprint=sprint,
            issues=issues,
            by_assignee=by_assignee,
            by_story=by_story,
        )
        logger.info(
            "리포트 생성 완료: %s (진행률 %.1f%%)",
            sprint.name,
            report.progress_percent,
        )
        return report

    def _group_by_assignee(self, issues: list[IssueInfo]) -> list[AssigneeReport]:
        """이슈를 담당자별로 그룹핑한다."""
        groups: dict[str, list[IssueInfo]] = {}
        for issue in issues:
            name = issue.assignee or "미배정"
            groups.setdefault(name, []).append(issue)

        return [
            AssigneeReport(name=name, issues=group)
            for name, group in sorted(groups.items())
        ]

    def _group_by_team(
        self, issues: list[IssueInfo], members: tuple[str, ...]
    ) -> list[AssigneeReport]:
        """지정된 팀 멤버에 해당하는 이슈를 담당자별로 그룹핑한다."""
        if not members:
            return []
        member_set = set(members)
        groups: dict[str, list[IssueInfo]] = {}
        for issue in issues:
            name = issue.assignee or "미배정"
            if name in member_set:
                groups.setdefault(name, []).append(issue)
        return [
            AssigneeReport(name=name, issues=group)
            for name, group in sorted(groups.items())
        ]

    def _group_by_story(self, issues: list[IssueInfo]) -> list[StoryReport]:
        """이슈를 스토리별로 그룹핑한다."""
        groups: dict[str, list[IssueInfo]] = {}
        story_summaries: dict[str, str] = {}

        for issue in issues:
            key = issue.story_key or issue.key
            summary = issue.story_summary or issue.summary
            groups.setdefault(key, []).append(issue)
            story_summaries[key] = summary

        return [
            StoryReport(
                story_key=key,
                story_summary=story_summaries[key],
                issues=group,
            )
            for key, group in sorted(groups.items())
        ]

    def _group_excluding_team(
        self, issues: list[IssueInfo], exclude_members: tuple[str, ...]
    ) -> list[AssigneeReport]:
        """지정된 팀 멤버를 제외한 이슈를 담당자별로 그룹핑한다."""
        exclude_set = set(exclude_members)
        groups: dict[str, list[IssueInfo]] = {}
        for issue in issues:
            name = issue.assignee or "미배정"
            if name not in exclude_set:
                groups.setdefault(name, []).append(issue)
        return [
            AssigneeReport(name=name, issues=group)
            for name, group in sorted(groups.items())
        ]

    def generate_project_report(
        self,
        project_key: str,
        statuses: tuple[str, ...] = (),
        dev_members: tuple[str, ...] = (),
    ) -> SprintReport | None:
        """프로젝트 키 기반으로 이슈 리포트를 생성한다.

        스프린트 보드가 없는 프로젝트(예: QA)용으로,
        JQL로 지정된 상태의 이슈를 조회한다.
        개발팀 멤버가 아닌 담당자는 라인으로 분류한다.

        Args:
            project_key: Jira 프로젝트 키.
            statuses: 필터링할 상태 목록. 비어있으면 전체 이슈 조회.
            dev_members: 개발팀 멤버 목록. 이 외 담당자는 라인으로 분류.
        """
        status_clause = ""
        if statuses:
            quoted = ", ".join(f'"{s}"' for s in statuses)
            status_clause = f"AND status IN ({quoted}) "
        jql = (
            f"project = {project_key} {status_clause}ORDER BY status ASC, updated DESC"
        )
        issues = self._jira.search_issues(jql)
        if not issues:
            return None

        sprint_placeholder = SprintInfo(
            id=0,
            name=f"{project_key} 이슈 현황",
            state="active",
        )
        by_assignee = self._group_by_assignee(issues)
        by_dev_team = self._group_by_team(issues, dev_members)
        by_line_team = self._group_excluding_team(issues, dev_members)
        by_story = self._group_by_story(issues)

        report = SprintReport(
            sprint=sprint_placeholder,
            issues=issues,
            by_assignee=by_assignee,
            by_story=by_story,
            by_dev_team=by_dev_team,
            by_line_team=by_line_team,
        )
        logger.info(
            "프로젝트 리포트 생성 완료: %s (이슈 %d건)",
            project_key,
            report.total_issues,
        )
        return report

    def format_slack_report(self, report: SprintReport) -> str:
        """슬랙 발송용 텍스트 리포트를 생성한다."""
        lines: list[str] = []
        lines.append(f"*{report.sprint.name}* 스프린트 현황")
        lines.append(
            f"진행률: {report.done_count}/{report.total_issues}"
            f" ({report.progress_percent:.0f}%)"
        )
        lines.append("")

        lines.append("*담당자별 현황:*")
        for ar in report.by_assignee:
            lines.append(
                f"  • {ar.name}: 완료 {ar.done_count} / 진행중"
                f" {ar.in_progress_count} / 대기 {ar.todo_count}"
            )

        return "\n".join(lines)
