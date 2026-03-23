"""burndown 모듈 테스트."""

from __future__ import annotations

from datetime import date

from sprintlens.burndown import (
    BurndownData,
    _get_workdays,
    _parse_period,
    calculate_burndown,
)
from sprintlens.schedule_parser import (
    MatchedIssue,
    ScheduleCategory,
    ScheduleSection,
    ScheduleTask,
    SprintSchedule,
)


class TestParsePeriod:
    """_parse_period 테스트."""

    def test_정상_기간_파싱(self):
        result = _parse_period("2026-03-16 ~ 2026-03-27")
        assert result == (date(2026, 3, 16), date(2026, 3, 27))

    def test_잘못된_형식(self):
        assert _parse_period("invalid") is None

    def test_빈_문자열(self):
        assert _parse_period("") is None


class TestGetWorkdays:
    """_get_workdays 테스트."""

    def test_주말_제외(self):
        # 2026-03-16(월) ~ 2026-03-22(일) → 평일 5일
        days = _get_workdays(date(2026, 3, 16), date(2026, 3, 22))
        assert len(days) == 5
        assert all(d.weekday() < 5 for d in days)

    def test_2주_스프린트(self):
        # 2026-03-16(월) ~ 2026-03-27(금) → 평일 10일
        days = _get_workdays(date(2026, 3, 16), date(2026, 3, 27))
        assert len(days) == 10


class TestCalculateBurndown:
    """calculate_burndown 테스트."""

    def _make_schedule(
        self,
        tasks: list[ScheduleTask] | None = None,
    ) -> SprintSchedule:
        if tasks is None:
            tasks = [
                ScheduleTask(
                    title="작업1",
                    estimate_days=5.0,
                    matched_issues=[
                        MatchedIssue(
                            key="GM-1",
                            summary="이슈1",
                            status="해결됨",
                            status_category="done",
                            resolved_date="2026-03-18",
                        )
                    ],
                ),
                ScheduleTask(
                    title="작업2",
                    estimate_days=3.0,
                    matched_issues=[],
                ),
                ScheduleTask(
                    title="작업3",
                    estimate_days=2.0,
                    matched_issues=[
                        MatchedIssue(
                            key="GM-2",
                            summary="이슈2",
                            status="열림",
                            status_category="new",
                        )
                    ],
                ),
            ]
        return SprintSchedule(
            title="테스트",
            period="2026-03-16 ~ 2026-03-27",
            sections=[
                ScheduleSection(
                    name="세부 일정",
                    categories=[
                        ScheduleCategory(name="테스트", tasks=tasks)
                    ],
                )
            ],
        )

    def test_번다운_데이터_생성(self):
        result = calculate_burndown(self._make_schedule())
        assert isinstance(result, BurndownData)
        assert result.total_points == 10.0

    def test_이상적_라인(self):
        result = calculate_burndown(self._make_schedule())
        assert result.ideal[0] == 10.0  # 시작
        assert result.ideal[-1] == 0.0  # 종료
        assert len(result.ideal) == 11  # 시작 + 작업일 10일

    def test_실제_라인_완료_반영(self):
        result = calculate_burndown(self._make_schedule())
        # 03/18(수)에 5.0일 완료 → 3번째 작업일 이후 5.0 감소
        # actual[0]=10.0(시작), actual[3]=5.0(03/18까지)
        assert result.actual[0] == 10.0
        assert result.actual[3] == 5.0  # 03/18까지

    def test_labels(self):
        result = calculate_burndown(self._make_schedule())
        assert result.labels[0] == "시작"
        assert "03/16" in result.labels[1]

    def test_미완료_이슈는_남은_포인트(self):
        result = calculate_burndown(self._make_schedule())
        # 마지막 actual 값은 5.0 (3.0 + 2.0 미완료)
        assert result.actual[-1] == 5.0

    def test_기간_없으면_None(self):
        schedule = SprintSchedule(title="테스트", period="")
        assert calculate_burndown(schedule) is None

    def test_to_dict(self):
        result = calculate_burndown(self._make_schedule())
        d = result.to_dict()
        assert "labels" in d
        assert "ideal" in d
        assert "actual" in d
        assert "today_index" in d
