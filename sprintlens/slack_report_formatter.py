"""슬랙 리포트 메시지 포매팅 모듈."""

from __future__ import annotations

from datetime import date

from sprintlens.burndown import _parse_period
from sprintlens.schedule_parser import SprintSchedule


def format_slack_report(
    schedule: SprintSchedule, *, dashboard_url: str = ""
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

    # Jira 미생성 작업
    no_jira = _get_tasks_by_status(schedule, "no_jira")
    if no_jira:
        lines.append(f":warning: *Jira 미생성 작업 {len(no_jira)}건*")
        for title, assignees in no_jira[:5]:
            names = ", ".join(assignees) if assignees else "미배정"
            lines.append(f"  • {title} - {names}")
        if len(no_jira) > 5:
            lines.append(f"  • ... 외 {len(no_jira) - 5}건")
        lines.append("")

    # 진행중 작업
    in_progress = _get_tasks_by_status(schedule, "in_progress")
    if in_progress:
        lines.append(f":arrows_counterclockwise: *진행중 작업 {len(in_progress)}건*")
        for title, assignees in in_progress[:5]:
            names = ", ".join(assignees) if assignees else "미배정"
            lines.append(f"  • {title} - {names}")
        if len(in_progress) > 5:
            lines.append(f"  • ... 외 {len(in_progress) - 5}건")
        lines.append("")

    # 완료 작업
    done = _get_tasks_by_status(schedule, "done")
    if done:
        lines.append(f":white_check_mark: *완료 작업 {len(done)}건*")
        for title, assignees in done[:5]:
            names = ", ".join(assignees) if assignees else "미배정"
            lines.append(f"  • {title} - {names}")
        if len(done) > 5:
            lines.append(f"  • ... 외 {len(done) - 5}건")
        lines.append("")

    # 대기 작업
    waiting = _get_tasks_by_status(schedule, "waiting")
    if waiting:
        lines.append(f":hourglass: *대기 작업 {len(waiting)}건*")
        for title, assignees in waiting[:5]:
            names = ", ".join(assignees) if assignees else "미배정"
            lines.append(f"  • {title} - {names}")
        if len(waiting) > 5:
            lines.append(f"  • ... 외 {len(waiting) - 5}건")
        lines.append("")

    # 상세 보기 링크
    if dashboard_url:
        lines.append(f":link: <{dashboard_url}|상세 보기>")

    return "\n".join(lines)


# ------------------------------------------------------------------
# 헬퍼
# ------------------------------------------------------------------


def _calc_d_day(period: str) -> int | None:
    """스프린트 종료일까지 남은 일수를 반환한다."""
    parsed = _parse_period(period)
    if not parsed:
        return None
    _, end_date = parsed
    return (end_date - date.today()).days


def _calc_progress(schedule: SprintSchedule) -> dict:
    """작업 진행률 통계를 계산한다."""
    total_count = 0
    done_count = 0
    done_estimate = 0.0

    for sec in schedule.sections:
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
) -> list[tuple[str, list[str]]]:
    """상태별 작업 목록을 반환한다. (제목, 담당자) 튜플 리스트."""
    result: list[tuple[str, list[str]]] = []

    for sec in schedule.sections:
        for cat in sec.categories:
            for task in cat.tasks:
                task_status = _classify_task(task)
                if task_status == status:
                    result.append((task.title, task.assignees))
    return result


def _classify_task(task) -> str:
    """task의 진행 상태를 분류한다."""
    if not task.matched_issues:
        if task.match_confidence == "none":
            return "no_jira"
        return "unknown"

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
