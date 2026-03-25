"""매칭되지 않은 Jira 이슈를 '추가된 일정' 섹션으로 빌드하는 모듈."""

from __future__ import annotations

from sprintlens.jira_service import IssueInfo
from sprintlens.logging_config import get_logger
from sprintlens.schedule_parser import (
    MatchedIssue,
    ScheduleCategory,
    ScheduleSection,
    ScheduleTask,
    SprintSchedule,
)

logger = get_logger(__name__)

ADDED_SECTION_NAME = "추가된 일정"


def collect_matched_keys(schedule: SprintSchedule) -> set[str]:
    """schedule에서 매칭된 모든 issue key를 수집한다."""
    keys: set[str] = set()
    for section in schedule.sections:
        for cat in section.categories:
            for task in cat.tasks:
                for mi in task.matched_issues:
                    keys.add(mi.key)
    return keys


def build_unmatched_section(
    issues: list[IssueInfo],
    matched_keys: set[str],
) -> ScheduleSection | None:
    """매칭되지 않은 이슈를 담당자별로 그룹핑하여 ScheduleSection을 생성한다.

    매칭되지 않은 이슈가 없으면 None을 반환한다.
    """
    unmatched = [i for i in issues if i.key not in matched_keys]
    if not unmatched:
        return None

    # 담당자별 그룹핑
    by_assignee: dict[str, list[IssueInfo]] = {}
    for issue in unmatched:
        assignee = issue.assignee or "미배정"
        by_assignee.setdefault(assignee, []).append(issue)

    categories: list[ScheduleCategory] = []
    for assignee in sorted(by_assignee):
        tasks = [
            ScheduleTask(
                title=issue.summary,
                assignees=[assignee] if assignee != "미배정" else [],
                matched_issues=[
                    MatchedIssue(
                        key=issue.key,
                        summary=issue.summary,
                        status=issue.status,
                        status_category=issue.status_category,
                        icon_url=issue.icon_url,
                        parent_key=issue.parent_key,
                        parent_summary=issue.parent_summary,
                        resolved_date=issue.resolved_date,
                    )
                ],
                match_confidence="high",
            )
            for issue in by_assignee[assignee]
        ]
        category_name = f"{assignee}의 작업" if assignee != "미배정" else "미배정 작업"
        categories.append(ScheduleCategory(name=category_name, tasks=tasks))

    logger.info(
        "추가된 일정: %d명의 담당자, %d개 이슈",
        len(categories),
        len(unmatched),
    )
    return ScheduleSection(name=ADDED_SECTION_NAME, categories=categories)
