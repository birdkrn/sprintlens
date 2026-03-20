"""schedule_matcher 모듈 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sprintlens.jira_service import IssueInfo
from sprintlens.schedule_matcher import ScheduleMatcher
from sprintlens.schedule_parser import (
    ScheduleCategory,
    ScheduleSection,
    ScheduleTask,
    SprintSchedule,
)


@pytest.fixture
def mock_gemini() -> MagicMock:
    """GeminiService mock."""
    return MagicMock()


@pytest.fixture
def mock_prompt_loader() -> MagicMock:
    """PromptLoader mock."""
    loader = MagicMock()
    loader.load.return_value = "프롬프트 텍스트"
    return loader


@pytest.fixture
def matcher(mock_gemini, mock_prompt_loader) -> ScheduleMatcher:
    return ScheduleMatcher(
        gemini_service=mock_gemini,
        prompt_loader=mock_prompt_loader,
    )


@pytest.fixture
def sample_schedule() -> SprintSchedule:
    return SprintSchedule(
        title="테스트 일정",
        sections=[
            ScheduleSection(
                name="세부 일정",
                categories=[
                    ScheduleCategory(
                        name="글로벌",
                        tasks=[
                            ScheduleTask(
                                title="GMG 빌드 및 전달",
                                assignees=["주세영"],
                                estimate_days=2.0,
                            ),
                            ScheduleTask(
                                title="GMG QA 이슈 대응",
                                assignees=["심민석"],
                                estimate_days=3.0,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_issues() -> list[IssueInfo]:
    return [
        IssueInfo(
            key="GM-101",
            summary="GMG 글로벌 빌드 전달",
            status="완료",
            status_category="done",
            assignee="주세영",
        ),
        IssueInfo(
            key="GM-102",
            summary="QA 이슈 대응",
            status="열림",
            status_category="new",
            assignee="심민석",
        ),
    ]


GEMINI_RESPONSE_JSON = """[
  {
    "schedule_task": "GMG 빌드 및 전달",
    "assignee": "주세영",
    "estimate_days": 2.0,
    "matched_issues": [
      {
        "key": "GM-101",
        "summary": "GMG 글로벌 빌드 전달",
        "status": "완료",
        "status_category": "done"
      }
    ],
    "match_confidence": "high"
  },
  {
    "schedule_task": "GMG QA 이슈 대응",
    "assignee": "심민석",
    "estimate_days": 3.0,
    "matched_issues": [
      {
        "key": "GM-102",
        "summary": "QA 이슈 대응",
        "status": "열림",
        "status_category": "new"
      }
    ],
    "match_confidence": "medium"
  }
]"""


class TestScheduleMatcher:
    """ScheduleMatcher 테스트."""

    def test_매칭_결과를_일정에_적용한다(
        self, matcher, mock_gemini, sample_schedule, sample_issues
    ):
        mock_response = MagicMock()
        mock_response.text = GEMINI_RESPONSE_JSON
        mock_gemini.generate_content.return_value = mock_response

        result = matcher.match(sample_schedule, sample_issues)

        task0 = result.sections[0].categories[0].tasks[0]
        assert task0.match_confidence == "high"
        assert len(task0.matched_issues) == 1
        assert task0.matched_issues[0].key == "GM-101"
        assert task0.matched_issues[0].status_category == "done"

        task1 = result.sections[0].categories[0].tasks[1]
        assert task1.match_confidence == "medium"
        assert task1.matched_issues[0].key == "GM-102"

    def test_Gemini에_프롬프트를_전송한다(
        self, matcher, mock_gemini, mock_prompt_loader, sample_schedule, sample_issues
    ):
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_gemini.generate_content.return_value = mock_response

        matcher.match(sample_schedule, sample_issues)

        mock_prompt_loader.load.assert_called_once()
        mock_gemini.generate_content.assert_called_once()

    def test_빈_이슈_목록도_처리한다(self, matcher, mock_gemini, sample_schedule):
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_gemini.generate_content.return_value = mock_response

        result = matcher.match(sample_schedule, [])
        assert result is not None


class TestParseResponse:
    """_parse_response 정적 메서드 테스트."""

    def test_정상_JSON_파싱(self):
        result = ScheduleMatcher._parse_response('[{"key": "value"}]')
        assert result == [{"key": "value"}]

    def test_코드_블록_감싸인_JSON(self):
        result = ScheduleMatcher._parse_response(
            '```json\n[{"key": "value"}]\n```'
        )
        assert result == [{"key": "value"}]

    def test_잘못된_JSON은_빈_목록(self):
        result = ScheduleMatcher._parse_response("not json")
        assert result == []

    def test_빈_문자열은_빈_목록(self):
        result = ScheduleMatcher._parse_response("")
        assert result == []


class TestFormatMethods:
    """포맷팅 메서드 테스트."""

    def test_일정_포맷팅(self, sample_schedule):
        text = ScheduleMatcher._format_schedule_tasks(sample_schedule)
        assert "글로벌" in text
        assert "GMG 빌드 및 전달" in text
        assert "주세영" in text

    def test_이슈_포맷팅(self, sample_issues):
        text = ScheduleMatcher._format_jira_issues(sample_issues)
        assert "GM-101" in text
        assert "done" in text
