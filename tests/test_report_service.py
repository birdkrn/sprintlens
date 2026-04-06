"""report_service 모듈 테스트."""

from unittest.mock import MagicMock

from sprintlens.jira_service import IssueInfo, SprintInfo
from sprintlens.report_service import ReportService, SprintReport


class TestReportService:
    """ReportService 테스트."""

    def _make_issues(self) -> list[IssueInfo]:
        return [
            IssueInfo(
                key="TEST-1", summary="작업1", status="해결됨",
                status_category="done", assignee="김철수",
                story_key="TEST-100", story_summary="스토리A",
                issue_type="작업",
            ),
            IssueInfo(
                key="TEST-2", summary="작업2", status="작업 중",
                status_category="indeterminate", assignee="김철수",
                story_key="TEST-100", story_summary="스토리A",
                issue_type="작업",
            ),
            IssueInfo(
                key="TEST-3", summary="작업3", status="열림",
                status_category="new", assignee="이영희",
                story_key="TEST-101", story_summary="스토리B",
                issue_type="작업",
            ),
        ]

    def test_generate_sprint_report(self):
        """스프린트 리포트가 정상적으로 생성된다."""
        mock_jira = MagicMock()
        mock_jira.get_active_sprint.return_value = SprintInfo(
            id=1, name="Sprint 1", state="active"
        )
        mock_jira.get_sprint_issues.return_value = self._make_issues()

        service = ReportService(jira_service=mock_jira)
        report = service.generate_sprint_report()

        assert report is not None
        assert report.total_issues == 3
        assert report.done_count == 1
        assert len(report.by_assignee) == 2
        assert len(report.by_story) == 2

    def test_generate_sprint_report_no_sprint(self):
        """활성 스프린트가 없는 경우 None을 반환한다."""
        mock_jira = MagicMock()
        mock_jira.get_active_sprint.return_value = None

        service = ReportService(jira_service=mock_jira)
        assert service.generate_sprint_report() is None

