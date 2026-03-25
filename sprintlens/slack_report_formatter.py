"""슬랙 리포트 메시지 포매팅 모듈."""

from __future__ import annotations

from datetime import date, timedelta

from sprintlens.burndown import _parse_period
from sprintlens.schedule_parser import SprintSchedule
from sprintlens.unmatched_issues import ADDED_SECTION_NAME


def format_slack_report(
    schedule: SprintSchedule,
    *,
    dashboard_url: str = "",
    show_in_progress: int = 99,
    show_done: int = 5,
    show_waiting: int = 5,
) -> str:
    """SprintSchedule을 슬랙 mrkdwn 메시지로 포매팅한다."""
    lines: list[str] = []

    # 헤더 + D-day
    d_day = _calc_d_day(schedule.period)
    d_day_text = f" (D{d_day:+d})" if d_day is not None else ""
    lines.append(f":bar_chart: *{schedule.title}*{d_day_text}")
    lines.append("")

    # 진행률 요약
    stats = _calc_progress(schedule)
    bar = _progress_bar(stats["done_count"], stats["total_count"])
    lines.append(
        f":black_square_button: 진행률: {bar} "
        f"{stats['done_count']}/{stats['total_count']} 작업 "
        f"({stats['percent']:.0f}%)"
    )
    lines.append(
        f":black_square_button: 남은 추정일: "
        f"{stats['remaining_days']:.1f}일 / {schedule.total_estimate:.1f}일"
    )
    lines.append("")

    # 진행중 작업
    in_progress = _get_tasks_by_status(schedule, "in_progress")
    if in_progress:
        lines.append(
            f":arrows_counterclockwise: *진행중 작업 {len(in_progress)}건*"
        )
        _append_task_lines(lines, in_progress, show_in_progress)
        lines.append("")

    # 완료 작업
    done = _get_tasks_by_status(schedule, "done")
    if done:
        lines.append(f":white_check_mark: *완료 작업 {len(done)}건*")
        _append_task_lines(lines, done, show_done)
        lines.append("")

    # 대기 작업 (Jira 미생성 포함)
    waiting = _get_tasks_by_status(schedule, "waiting")
    no_jira = _get_tasks_by_status(schedule, "no_jira")
    all_waiting = waiting + no_jira
    if all_waiting:
        lines.append(f":hourglass: *대기 작업 {len(all_waiting)}건*")
        _append_task_lines(lines, all_waiting, show_waiting)
        lines.append("")

    # 추가된 일정
    added = _get_added_tasks(schedule)
    if added:
        lines.append(f":heavy_plus_sign: *추가된 일정 {len(added)}건*")
        _append_task_lines(lines, added, show_in_progress)
        lines.append("")

    # 상세 보기 링크
    if dashboard_url:
        lines.append(f":link: <{dashboard_url}|상세 보기>")

    return "\n".join(lines)


# ------------------------------------------------------------------
# 헬퍼
# ------------------------------------------------------------------


def _append_task_lines(
    lines: list[str],
    tasks: list[tuple[str, list[str], bool, str]],
    max_show: int,
) -> None:
    """작업 목록을 lines에 추가한다."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    for title, assignees, is_no_jira, resolved in tasks[:max_show]:
        names = ", ".join(assignees) if assignees else "미배정"
        prefix = ":new: " if resolved >= yesterday else ""
        suffix = " _(Jira 미생성)_" if is_no_jira else ""
        lines.append(f"  • {prefix}{title} - {names}{suffix}")
    remaining = len(tasks) - max_show
    if remaining > 0:
        lines.append(f"  • ... 외 {remaining}건")


def _calc_d_day(period: str) -> int | None:
    """스프린트 종료일까지 남은 일수를 반환한다."""
    parsed = _parse_period(period)
    if not parsed:
        return None
    _, end_date = parsed
    return (end_date - date.today()).days


def _calc_progress(schedule: SprintSchedule) -> dict:
    """작업 진행률 통계를 계산한다 (추가된 일정 제외)."""
    total_count = 0
    done_count = 0
    done_estimate = 0.0

    for sec in schedule.sections:
        if sec.name == ADDED_SECTION_NAME:
            continue
        for cat in sec.categories:
            for task in cat.tasks:
                total_count += 1
                if task.matched_issues and all(
                    mi.status_category == "done"
                    for mi in task.matched_issues
                ):
                    done_count += 1
                    done_estimate += task.estimate_days

    remaining = schedule.total_estimate - done_estimate
    percent = (done_count / total_count * 100) if total_count else 0

    return {
        "total_count": total_count,
        "done_count": done_count,
        "percent": percent,
        "remaining_days": remaining,
    }


def _get_tasks_by_status(
    schedule: SprintSchedule, status: str
) -> list[tuple[str, list[str], bool, str]]:
    """상태별 작업 목록을 반환한다.

    Returns:
        (제목, 담당자, Jira미생성여부, resolved_date) 튜플 리스트.
        done 상태는 최근 완료순으로 정렬한다.
    """
    result: list[tuple[str, list[str], bool, str]] = []

    for sec in schedule.sections:
        if sec.name == ADDED_SECTION_NAME:
            continue
        for cat in sec.categories:
            for task in cat.tasks:
                task_status = _classify_task(task)
                if task_status == status:
                    is_no_jira = task_status == "no_jira"
                    # 가장 최근 resolved_date 추출
                    resolved = ""
                    if task.matched_issues:
                        dates = [
                            mi.resolved_date
                            for mi in task.matched_issues
                            if mi.resolved_date
                        ]
                        if dates:
                            resolved = max(dates)
                    result.append(
                        (task.title, task.assignees, is_no_jira, resolved)
                    )

    # done 상태는 최근 완료순 (내림차순)
    if status == "done":
        result.sort(key=lambda x: x[3], reverse=True)

    return [(t, a, n, r) for t, a, n, r in result]


def _get_added_tasks(
    schedule: SprintSchedule,
) -> list[tuple[str, list[str], bool, str]]:
    """추가된 일정 섹션의 작업 목록을 반환한다."""
    result: list[tuple[str, list[str], bool, str]] = []
    for sec in schedule.sections:
        if sec.name != ADDED_SECTION_NAME:
            continue
        for cat in sec.categories:
            for task in cat.tasks:
                resolved = ""
                if task.matched_issues:
                    dates = [
                        mi.resolved_date
                        for mi in task.matched_issues
                        if mi.resolved_date
                    ]
                    if dates:
                        resolved = max(dates)
                result.append(
                    (task.title, task.assignees, False, resolved)
                )
    return result


def _classify_task(task) -> str:
    """task의 진행 상태를 분류한다."""
    if not task.matched_issues:
        if task.match_confidence == "none":
            return "no_jira"
        return "waiting"

    all_done = all(
        mi.status_category == "done" for mi in task.matched_issues
    )
    if all_done:
        return "done"

    any_progress = any(
        mi.status_category == "indeterminate"
        for mi in task.matched_issues
    )
    if any_progress:
        return "in_progress"

    return "waiting"


def _progress_bar(done: int, total: int, length: int = 10) -> str:
    """텍스트 프로그레스 바를 생성한다."""
    if total == 0:
        return "░" * length
    filled = round(done / total * length)
    return "█" * filled + "░" * (length - filled)
