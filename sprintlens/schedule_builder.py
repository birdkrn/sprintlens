"""스프린트 일정 빌드 공통 모듈.

Confluence 일정 파싱 → Jira 이슈 매칭 → 추가 일정 섹션 생성을
하나의 함수로 통합한다. routes.py와 app.py에서 공통으로 사용한다.
"""

from __future__ import annotations

from sprintlens.logging_config import get_logger
from sprintlens.schedule_parser import SprintSchedule, parse_schedule_html
from sprintlens.unmatched_issues import build_unmatched_section, collect_matched_keys

logger = get_logger(__name__)


def build_schedule(
    *,
    confluence_service,
    page_id: str,
    jira_service=None,
    schedule_matcher=None,
    match_store=None,
    program_team_members: tuple[str, ...] = (),
) -> SprintSchedule | None:
    """Confluence 일정을 가져와 파싱하고, Jira 이슈를 AI로 매칭한다.

    Args:
        confluence_service: Confluence API 클라이언트.
        page_id: Confluence 스프린트 일정 페이지 ID.
        jira_service: Jira API 클라이언트 (선택).
        schedule_matcher: AI 매칭 서비스 (선택).
        match_store: 매칭 결과 저장소 (선택).
        program_team_members: 프로그램팀 멤버 필터 (선택).

    Returns:
        매칭 완료된 SprintSchedule. 실패 시 None.
    """
    if not confluence_service or not page_id:
        return None

    try:
        page = confluence_service.get_page(page_id)
        schedule = parse_schedule_html(page.title, page.body_html)

        if schedule_matcher and jira_service:
            sprint = jira_service.get_active_sprint()
            if sprint:
                issues = jira_service.get_sprint_issues(
                    sprint.id, expand_changelog=True
                )
                if program_team_members:
                    members = set(program_team_members)
                    issues = [
                        i for i in issues if i.assignee in members
                    ]
                schedule_matcher.match(
                    schedule,
                    issues,
                    match_store=match_store,
                    page_id=page_id,
                )

                matched_keys = collect_matched_keys(schedule)
                unmatched_section = build_unmatched_section(
                    issues, matched_keys
                )
                if unmatched_section:
                    schedule.sections.append(unmatched_section)

        return schedule
    except Exception:
        logger.exception("스프린트 일정 빌드 실패")
        return None
