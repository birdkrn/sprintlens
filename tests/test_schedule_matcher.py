"""schedule_matcher 모듈 테스트."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sprintlens.jira_service import IssueInfo
from sprintlens.match_store import MatchStore
from sprintlens.schedule_matcher import (
    ScheduleMatcher,
    _compute_issues_hash,
    _compute_schedule_hash,
)
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


class TestMatchStoreIntegration:
    """MatchStore 연동 테스트."""

    @pytest.fixture
    def match_store(self, tmp_path: Path) -> MatchStore:
        return MatchStore(db_path=tmp_path / "matches.db")

    def test_매칭_결과를_저장하고_재사용한다(
        self, matcher, mock_gemini, sample_schedule, sample_issues, match_store
    ):
        """첫 호출은 Gemini 사용, 두 번째 호출은 저장된 결과 재사용."""
        mock_response = MagicMock()
        mock_response.text = GEMINI_RESPONSE_JSON
        mock_gemini.generate_content.return_value = mock_response

        # 첫 번째 호출: Gemini 매칭 + 저장
        matcher.match(
            sample_schedule, sample_issues,
            match_store=match_store, page_id="test_page",
        )
        assert mock_gemini.generate_content.call_count == 1

        # 새 schedule 객체 생성 (matched_issues 초기화 상태)
        fresh_schedule = SprintSchedule(
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

        # 두 번째 호출: 저장된 매칭 재사용 (Gemini 호출 안 함)
        matcher.match(
            fresh_schedule, sample_issues,
            match_store=match_store, page_id="test_page",
        )
        assert mock_gemini.generate_content.call_count == 1  # 증가 안 함

        # 매칭 결과가 정상 적용되었는지 확인
        task0 = fresh_schedule.sections[0].categories[0].tasks[0]
        assert task0.matched_issues[0].key == "GM-101"

    def test_일정_변경_시_재매칭한다(
        self, matcher, mock_gemini, sample_schedule, sample_issues, match_store
    ):
        """일정 항목이 변경되면 Gemini를 다시 호출한다."""
        mock_response = MagicMock()
        mock_response.text = GEMINI_RESPONSE_JSON
        mock_gemini.generate_content.return_value = mock_response

        # 첫 매칭
        matcher.match(
            sample_schedule, sample_issues,
            match_store=match_store, page_id="test_page",
        )

        # 일정에 새 task 추가
        changed_schedule = SprintSchedule(
            title="테스트 일정",
            sections=[
                ScheduleSection(
                    name="세부 일정",
                    categories=[
                        ScheduleCategory(
                            name="글로벌",
                            tasks=[
                                ScheduleTask(title="GMG 빌드 및 전달", assignees=["주세영"]),
                                ScheduleTask(title="GMG QA 이슈 대응", assignees=["심민석"]),
                                ScheduleTask(title="새로운 작업", assignees=["이진명"]),
                            ],
                        ),
                    ],
                ),
            ],
        )

        matcher.match(
            changed_schedule, sample_issues,
            match_store=match_store, page_id="test_page",
        )
        assert mock_gemini.generate_content.call_count == 2  # 재매칭

    def test_이슈_변경_시_재매칭한다(
        self, matcher, mock_gemini, sample_schedule, sample_issues, match_store
    ):
        """이슈 목록이 변경되면 Gemini를 다시 호출한다."""
        mock_response = MagicMock()
        mock_response.text = GEMINI_RESPONSE_JSON
        mock_gemini.generate_content.return_value = mock_response

        matcher.match(
            sample_schedule, sample_issues,
            match_store=match_store, page_id="test_page",
        )

        # 새 이슈 추가
        new_issues = sample_issues + [
            IssueInfo(key="GM-103", summary="새 이슈", status="열림"),
        ]

        # 새 schedule (matched_issues 초기화 상태)
        fresh_schedule = SprintSchedule(
            title="테스트 일정",
            sections=[
                ScheduleSection(
                    name="세부 일정",
                    categories=[
                        ScheduleCategory(
                            name="글로벌",
                            tasks=[
                                ScheduleTask(title="GMG 빌드 및 전달", assignees=["주세영"]),
                                ScheduleTask(title="GMG QA 이슈 대응", assignees=["심민석"]),
                            ],
                        ),
                    ],
                ),
            ],
        )

        matcher.match(
            fresh_schedule, new_issues,
            match_store=match_store, page_id="test_page",
        )
        assert mock_gemini.generate_content.call_count == 2  # 재매칭

    def test_match_store_없이도_기존처럼_동작한다(
        self, matcher, mock_gemini, sample_schedule, sample_issues
    ):
        """하위 호환성: match_store를 전달하지 않아도 동작한다."""
        mock_response = MagicMock()
        mock_response.text = GEMINI_RESPONSE_JSON
        mock_gemini.generate_content.return_value = mock_response

        result = matcher.match(sample_schedule, sample_issues)

        assert result is not None
        task0 = result.sections[0].categories[0].tasks[0]
        assert task0.matched_issues[0].key == "GM-101"


class TestHashFunctions:
    """해시 계산 함수 테스트."""

    def test_같은_일정은_같은_해시를_반환한다(self, sample_schedule):
        h1 = _compute_schedule_hash(sample_schedule)
        h2 = _compute_schedule_hash(sample_schedule)
        assert h1 == h2

    def test_다른_일정은_다른_해시를_반환한다(self, sample_schedule):
        h1 = _compute_schedule_hash(sample_schedule)

        changed = SprintSchedule(
            title="다른 일정",
            sections=[
                ScheduleSection(
                    name="세부 일정",
                    categories=[
                        ScheduleCategory(
                            name="글로벌",
                            tasks=[
                                ScheduleTask(title="새 작업", assignees=["김철수"]),
                            ],
                        ),
                    ],
                ),
            ],
        )
        h2 = _compute_schedule_hash(changed)
        assert h1 != h2

    def test_같은_이슈는_같은_해시를_반환한다(self, sample_issues):
        h1 = _compute_issues_hash(sample_issues)
        h2 = _compute_issues_hash(sample_issues)
        assert h1 == h2

    def test_이슈_순서가_달라도_같은_해시를_반환한다(self, sample_issues):
        h1 = _compute_issues_hash(sample_issues)
        h2 = _compute_issues_hash(list(reversed(sample_issues)))
        assert h1 == h2

    def test_이슈_추가되면_다른_해시를_반환한다(self, sample_issues):
        h1 = _compute_issues_hash(sample_issues)
        h2 = _compute_issues_hash(
            sample_issues + [IssueInfo(key="GM-999", summary="새 이슈", status="열림")]
        )
        assert h1 != h2
