"""unmatched_issues 모듈 테스트."""

from __future__ import annotations

import pytest

from sprintlens.jira_service import IssueInfo
from sprintlens.schedule_parser import (
    MatchedIssue,
    ScheduleCategory,
    ScheduleSection,
    ScheduleTask,
    SprintSchedule,
)
from sprintlens.unmatched_issues import (
    ADDED_SECTION_NAME,
    build_unmatched_section,
    collect_matched_keys,
)


@pytest.fixture
def schedule_with_matches() -> SprintSchedule:
    """매칭된 이슈가 있는 일정."""
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
                                title="빌드 전달",
                                matched_issues=[
                                    MatchedIssue(key="GM-101", summary="빌드", status="완료"),
                                    MatchedIssue(key="GM-102", summary="테스트", status="진행중"),
                                ],
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
        IssueInfo(key="GM-101", summary="빌드", status="완료", status_category="done", assignee="홍길동"),
        IssueInfo(key="GM-102", summary="테스트", status="진행중", status_category="indeterminate", assignee="홍길동"),
        IssueInfo(key="GM-200", summary="긴급 버그 수정", status="열림", status_category="new", assignee="김철수"),
        IssueInfo(key="GM-201", summary="성능 개선", status="진행중", status_category="indeterminate", assignee="홍길동"),
        IssueInfo(key="GM-202", summary="미배정 이슈", status="열림", status_category="new", assignee=None),
    ]


class TestCollectMatchedKeys:
    """collect_matched_keys 테스트."""

    def test_매칭된_이슈_키를_수집한다(self, schedule_with_matches):
        keys = collect_matched_keys(schedule_with_matches)
        assert keys == {"GM-101", "GM-102"}

    def test_매칭_없으면_빈_셋을_반환한다(self):
        schedule = SprintSchedule(
            title="빈 일정",
            sections=[
                ScheduleSection(
                    name="세부 일정",
                    categories=[
                        ScheduleCategory(
                            name="테스트",
                            tasks=[ScheduleTask(title="작업1")],
                        ),
                    ],
                ),
            ],
        )
        assert collect_matched_keys(schedule) == set()


class TestBuildUnmatchedSection:
    """build_unmatched_section 테스트."""

    def test_매칭되지_않은_이슈를_담당자별로_그룹핑한다(self, sample_issues):
        matched_keys = {"GM-101", "GM-102"}
        section = build_unmatched_section(sample_issues, matched_keys)

        assert section is not None
        assert section.name == ADDED_SECTION_NAME
        # 담당자: 김철수, 홍길동, 미배정 → 3개 카테고리
        assert len(section.categories) == 3

        # 카테고리 이름 확인 (정렬됨)
        names = [c.name for c in section.categories]
        assert "김철수의 작업" in names
        assert "홍길동의 작업" in names
        assert "미배정 작업" in names

    def test_모든_이슈가_매칭되면_None을_반환한다(self, sample_issues):
        all_keys = {i.key for i in sample_issues}
        section = build_unmatched_section(sample_issues, all_keys)
        assert section is None

    def test_이슈를_ScheduleTask로_변환한다(self, sample_issues):
        matched_keys = {"GM-101", "GM-102", "GM-201", "GM-202"}
        section = build_unmatched_section(sample_issues, matched_keys)

        assert section is not None
        # GM-200만 남음 (김철수)
        assert len(section.categories) == 1
        cat = section.categories[0]
        assert cat.name == "김철수의 작업"
        assert len(cat.tasks) == 1

        task = cat.tasks[0]
        assert task.title == "긴급 버그 수정"
        assert task.assignees == ["김철수"]
        assert len(task.matched_issues) == 1
        assert task.matched_issues[0].key == "GM-200"
        assert task.match_confidence == "high"

    def test_빈_이슈_목록이면_None을_반환한다(self):
        section = build_unmatched_section([], set())
        assert section is None

    def test_이슈를_상태별로_정렬한다(self):
        """작업 중 → 열림 → 다시 열림 → 해결됨 → 닫힘 순으로 정렬."""
        issues = [
            IssueInfo(key="A-1", summary="닫힌 이슈", status="닫힘", assignee="홍길동"),
            IssueInfo(key="A-2", summary="작업 중 이슈", status="작업 중", assignee="홍길동"),
            IssueInfo(key="A-3", summary="해결된 이슈", status="해결됨", assignee="홍길동"),
            IssueInfo(key="A-4", summary="열린 이슈", status="열림", assignee="홍길동"),
        ]
        section = build_unmatched_section(issues, set())

        assert section is not None
        tasks = section.categories[0].tasks
        statuses = [t.matched_issues[0].status for t in tasks]
        assert statuses == ["작업 중", "열림", "해결됨", "닫힘"]
