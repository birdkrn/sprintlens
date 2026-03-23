"""스프린트 번다운 차트 데이터 계산 모듈."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import date, timedelta

from sprintlens.logging_config import get_logger
from sprintlens.schedule_parser import SprintSchedule

logger = get_logger(__name__)


@dataclass
class BurndownData:
    """번다운 차트 렌더링에 필요한 데이터."""

    labels: list[str] = field(default_factory=list)  # "03/16", "03/17", ...
    ideal: list[float] = field(default_factory=list)  # 이상적 번다운
    actual: list[float] = field(default_factory=list)  # 실제 번다운
    today_index: int | None = None  # 오늘 날짜의 인덱스 (없으면 None)
    total_points: float = 0.0

    def to_dict(self) -> dict:
        """JSON 직렬화용 딕셔너리로 변환한다."""
        return {
            "labels": self.labels,
            "ideal": self.ideal,
            "actual": self.actual,
            "today_index": self.today_index,
            "total_points": self.total_points,
        }


def _parse_period(period: str) -> tuple[date, date] | None:
    """'2026-03-16 ~ 2026-03-27' 형식의 기간을 파싱한다."""
    parts = period.replace("~", " ").split()
    dates = [p.strip() for p in parts if "-" in p]
    if len(dates) < 2:
        return None
    try:
        start = date.fromisoformat(dates[0])
        end = date.fromisoformat(dates[1])
        return start, end
    except ValueError:
        return None


def _get_workdays(start: date, end: date) -> list[date]:
    """시작~종료 사이의 평일(월~금) 목록을 반환한다."""
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 0=월 ~ 4=금
            days.append(current)
        current += timedelta(days=1)
    return days


def calculate_burndown(schedule: SprintSchedule) -> BurndownData | None:
    """SprintSchedule에서 번다운 차트 데이터를 계산한다.

    각 task의 완료 여부는 매칭된 Jira 이슈의 상태로 판단한다:
    - 모든 매칭 이슈가 done → task 완료 (resolved_date 기준)
    - 매칭 이슈 없음 → 미완료
    """
    period = _parse_period(schedule.period)
    if not period:
        logger.warning("스프린트 기간 파싱 실패: %s", schedule.period)
        return None

    start_date, end_date = period
    workdays = _get_workdays(start_date, end_date)
    if not workdays:
        return None

    total_points = schedule.total_estimate

    # 이상적 번다운: 매 작업일마다 균등 감소
    daily_burn = total_points / len(workdays) if workdays else 0
    ideal = [
        round(total_points - daily_burn * i, 1)
        for i in range(len(workdays) + 1)
    ]
    # 첫날은 total, 마지막은 0 (workdays + 1개 포인트)
    # labels도 시작 전 날 포함하지 않고, 각 작업일 끝 기준
    labels = ["시작"] + [d.strftime("%m/%d") for d in workdays]

    # task별 완료 날짜 수집
    completed: list[tuple[date, float]] = []  # (완료일, 추정일)
    for section in schedule.sections:
        for cat in section.categories:
            for task in cat.tasks:
                if not task.matched_issues:
                    continue
                # 모든 매칭 이슈가 done인지 확인
                all_done = all(
                    mi.status_category == "done"
                    for mi in task.matched_issues
                )
                if not all_done:
                    continue

                # 가장 늦게 완료된 이슈의 날짜
                resolved_dates = [
                    mi.resolved_date
                    for mi in task.matched_issues
                    if mi.resolved_date
                ]
                if resolved_dates:
                    latest = max(resolved_dates)
                    with contextlib.suppress(ValueError):
                        completed.append(
                            (date.fromisoformat(latest), task.estimate_days)
                        )

    # 실제 번다운: 날짜별 남은 포인트 계산
    # 완료일별 포인트 합산 (O(n))
    daily_done: dict[date, float] = {}
    for comp_date, pts in completed:
        daily_done[comp_date] = daily_done.get(comp_date, 0.0) + pts

    # 누적합으로 계산 (O(n))
    actual: list[float] = [total_points]
    cumulative_done = 0.0
    today = date.today()
    today_index: int | None = None

    for i, workday in enumerate(workdays):
        # 이 작업일까지의 완료 포인트를 누적
        for d in sorted(daily_done):
            if d <= workday:
                cumulative_done += daily_done.pop(d)
        actual.append(round(total_points - cumulative_done, 1))

        if workday == today:
            today_index = i + 1  # +1: "시작" 오프셋

    # 오늘이 스프린트 기간을 지났지만 마지막 작업일 이후면
    if today_index is None and today > workdays[-1]:
        today_index = len(workdays)

    # 미래 날짜는 actual에서 제거 (오늘까지만 표시)
    if today_index is not None:
        actual = actual[: today_index + 1]

    data = BurndownData(
        labels=labels,
        ideal=ideal,
        actual=actual,
        today_index=today_index,
        total_points=total_points,
    )
    logger.info(
        "번다운 차트 계산: 총 %.1f일, 완료 %.1f일, 작업일 %d일",
        total_points,
        total_points - (actual[-1] if actual else total_points),
        len(workdays),
    )
    return data
