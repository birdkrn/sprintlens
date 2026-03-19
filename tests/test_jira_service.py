"""JiraService 모듈 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from sprintlens.jira_service import (
    IssueInfo,
    JiraService,
    ProjectInfo,
    SprintInfo,
)

# ------------------------------------------------------------------
# 픽스처
# ------------------------------------------------------------------


@pytest.fixture
def mock_jira():
    """atlassian Jira 객체를 모킹한다."""
    with patch("sprintlens.jira_service.Jira") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def service(mock_jira) -> JiraService:
    """테스트용 JiraService 인스턴스를 생성한다."""
    return JiraService(
        base_url="https://jira.test.com",
        username="test_user",
        password="test_password",
        board_id="658",
    )


# ------------------------------------------------------------------
# 스프린트 데이터
# ------------------------------------------------------------------

ACTIVE_SPRINT_DATA = {
    "id": 883,
    "name": "3월 2회차(26.03.16~26.03.27)",
    "state": "active",
    "startDate": "2026-03-16T09:00:12.082+09:00",
    "endDate": "2026-03-27T23:59:00.000+09:00",
    "goal": "릴리즈 준비",
}

CLOSED_SPRINT_DATA = {
    "id": 880,
    "name": "3월 1회차(26.03.02~26.03.13)",
    "state": "closed",
    "startDate": "2026-03-02T09:00:00.000+09:00",
    "endDate": "2026-03-13T23:59:00.000+09:00",
    "goal": "",
}


# ------------------------------------------------------------------
# 이슈 데이터
# ------------------------------------------------------------------

ISSUE_WITH_PARENT = {
    "key": "G2M-101",
    "fields": {
        "summary": "로그인 기능 구현",
        "status": {
            "name": "진행 중",
            "statusCategory": {"key": "indeterminate"},
        },
        "assignee": {"displayName": "홍길동"},
        "parent": {
            "key": "G2M-100",
            "fields": {"summary": "인증 시스템 개발"},
        },
        "issuetype": {"name": "하위 작업"},
    },
}

ISSUE_WITHOUT_PARENT = {
    "key": "G2M-102",
    "fields": {
        "summary": "API 문서 작성",
        "status": {
            "name": "완료",
            "statusCategory": {"key": "done"},
        },
        "assignee": None,
        "parent": None,
        "issuetype": {"name": "작업"},
    },
}


# ------------------------------------------------------------------
# 프로젝트 데이터
# ------------------------------------------------------------------

PROJECT_DATA = {
    "key": "G2M",
    "name": "Game2Market",
    "description": "게임 마켓 프로젝트",
    "lead": {"displayName": "김팀장"},
}


# ==================================================================
# 테스트
# ==================================================================


class TestGetProjectInfo:
    """get_project_info 테스트."""

    def test_프로젝트_정보를_조회한다(self, service, mock_jira):
        mock_jira.project.return_value = PROJECT_DATA

        result = service.get_project_info("G2M")

        assert isinstance(result, ProjectInfo)
        assert result.key == "G2M"
        assert result.name == "Game2Market"
        assert result.lead == "김팀장"
        mock_jira.project.assert_called_once_with("G2M")

    def test_리드_없는_프로젝트를_처리한다(self, service, mock_jira):
        data = {**PROJECT_DATA, "lead": {}}
        mock_jira.project.return_value = data

        result = service.get_project_info("G2M")

        assert result.lead == ""


class TestGetActiveSprint:
    """get_active_sprint 테스트."""

    def test_활성_스프린트를_반환한다(self, service, mock_jira):
        mock_jira.get_all_sprints_from_board.return_value = {
            "values": [ACTIVE_SPRINT_DATA]
        }

        result = service.get_active_sprint()

        assert isinstance(result, SprintInfo)
        assert result.id == 883
        assert result.state == "active"
        assert result.goal == "릴리즈 준비"

    def test_활성_스프린트가_없으면_None을_반환한다(self, service, mock_jira):
        mock_jira.get_all_sprints_from_board.return_value = {"values": []}

        result = service.get_active_sprint()

        assert result is None


class TestGetBoardSprints:
    """get_board_sprints 테스트."""

    def test_상태별_스프린트_목록을_반환한다(self, service, mock_jira):
        mock_jira.get_all_sprints_from_board.return_value = {
            "values": [ACTIVE_SPRINT_DATA, CLOSED_SPRINT_DATA]
        }

        result = service.get_board_sprints()

        assert len(result) == 2
        assert all(isinstance(s, SprintInfo) for s in result)

    def test_상태_필터를_전달한다(self, service, mock_jira):
        mock_jira.get_all_sprints_from_board.return_value = {"values": []}

        service.get_board_sprints(state="closed")

        mock_jira.get_all_sprints_from_board.assert_called_once_with(
            "658", state="closed"
        )


class TestGetSprintIssues:
    """get_sprint_issues 테스트."""

    def test_스프린트_이슈_목록을_반환한다(self, service, mock_jira):
        mock_jira.get_sprint_issues.return_value = {
            "issues": [ISSUE_WITH_PARENT, ISSUE_WITHOUT_PARENT]
        }

        result = service.get_sprint_issues(883)

        assert len(result) == 2
        assert result[0].key == "G2M-101"
        assert result[0].assignee == "홍길동"
        assert result[0].story_key == "G2M-100"
        assert result[1].assignee is None
        assert result[1].story_key is None

    def test_이슈가_없으면_빈_목록을_반환한다(self, service, mock_jira):
        mock_jira.get_sprint_issues.return_value = {"issues": []}

        result = service.get_sprint_issues(883)

        assert result == []


class TestGetIssueDetail:
    """get_issue_detail 테스트."""

    def test_이슈_상세를_조회한다(self, service, mock_jira):
        mock_jira.issue.return_value = ISSUE_WITH_PARENT

        result = service.get_issue_detail("G2M-101")

        assert isinstance(result, IssueInfo)
        assert result.key == "G2M-101"
        assert result.summary == "로그인 기능 구현"
        assert result.issue_type == "하위 작업"
        mock_jira.issue.assert_called_once_with("G2M-101")


class TestSearchIssues:
    """search_issues 테스트."""

    def test_JQL_검색_결과를_반환한다(self, service, mock_jira):
        mock_jira.jql.return_value = {
            "issues": [ISSUE_WITH_PARENT, ISSUE_WITHOUT_PARENT],
            "total": 2,
        }

        result = service.search_issues('project = G2M AND status = "진행 중"')

        assert len(result) == 2
        mock_jira.jql.assert_called_once()

    def test_페이지네이션을_처리한다(self, service, mock_jira):
        """결과가 여러 페이지에 걸칠 때 자동으로 모두 가져온다."""
        mock_jira.jql.side_effect = [
            {"issues": [ISSUE_WITH_PARENT], "total": 2},
            {"issues": [ISSUE_WITHOUT_PARENT], "total": 2},
        ]

        result = service.search_issues("project = G2M", max_results=200)

        assert len(result) == 2
        assert mock_jira.jql.call_count == 2

    def test_빈_결과를_처리한다(self, service, mock_jira):
        mock_jira.jql.return_value = {"issues": [], "total": 0}

        result = service.search_issues("project = NONE")

        assert result == []
