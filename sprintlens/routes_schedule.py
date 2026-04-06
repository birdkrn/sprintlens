"""프로그램팀 일정 관련 라우트 모듈."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from sprintlens.burndown import calculate_burndown
from sprintlens.jira_service import IssueInfo
from sprintlens.logging_config import get_logger
from sprintlens.schedule_builder import build_schedule
from sprintlens.schedule_matcher import apply_manual_overrides
from sprintlens.schedule_parser import SprintSchedule
from sprintlens.slack_report_formatter import format_slack_report
from sprintlens.unmatched_issues import ADDED_SECTION_NAME

logger = get_logger(__name__)

schedule_pages = Blueprint("schedule_pages", __name__)
schedule_api = Blueprint("schedule_api", __name__, url_prefix="/api")


def init_schedule_routes(
    *,
    config,
    confluence_service,
    jira_service,
    schedule_matcher,
    cache_store,
    settings_store,
    match_store,
    manual_match_store,
    slack_service=None,
    schedule_builder=None,
    get_setting_fn,
) -> None:
    """프로그램팀 일정 관련 라우트를 등록한다."""

    def _schedule_cache_key() -> str:
        return f"schedule:{get_setting_fn('confluence_sprint_page_id')}"

    # ------------------------------------------------------------------
    # HTMX 파셜 라우트
    # ------------------------------------------------------------------

    @schedule_pages.route("/partials/schedule")
    def partials_schedule():
        """HTMX 파셜: 프로그램팀 일정 (로딩 화면)."""
        refresh = request.args.get("refresh") == "1"
        return render_template(
            "partials/schedule_loading.html",
            refresh=refresh,
            config=config,
        )

    @schedule_pages.route("/partials/schedule/data")
    def partials_schedule_data():
        """HTMX 파셜: 프로그램팀 일정 데이터 (비동기 로드)."""
        refresh = request.args.get("refresh") == "1"
        sprint_schedule, updated_at = _build_schedule_cached(
            force_refresh=refresh
        )
        burndown = None
        if sprint_schedule:
            burndown = calculate_burndown(sprint_schedule)
        return render_template(
            "partials/schedule.html",
            schedule=sprint_schedule,
            burndown=burndown,
            updated_at=updated_at,
            config=config,
        )

    # ------------------------------------------------------------------
    # API 라우트
    # ------------------------------------------------------------------

    @schedule_api.route("/slack/test", methods=["POST"])
    def api_slack_test():
        """슬랙 리포트를 즉시 테스트 발송한다."""
        if not slack_service:
            return jsonify({"error": "Slack Webhook URL이 설정되지 않았습니다."}), 503
        if not schedule_builder:
            return jsonify({"error": "일정 빌더가 초기화되지 않았습니다."}), 503

        schedule = schedule_builder()
        if not schedule:
            return jsonify({"error": "스프린트 일정을 가져올 수 없습니다."}), 500

        text = format_slack_report(
            schedule,
            dashboard_url=config.slack_dashboard_url,
            show_in_progress=config.slack_show_in_progress,
            show_done=config.slack_show_done,
            show_waiting=config.slack_show_waiting,
            show_added=config.slack_show_added,
        )
        success = slack_service.send_message(text)
        if success:
            return jsonify({"ok": True, "message": "슬랙 발송 완료"})
        return jsonify({"error": "슬랙 발송 실패"}), 500

    @schedule_api.route("/schedule/tasks")
    def api_schedule_tasks():
        """매칭 이동 모달용 작업 목록 API."""
        schedule, _ = _build_schedule_cached()
        if not schedule:
            return jsonify({"error": "일정을 불러올 수 없습니다."}), 404

        tasks_list = []
        for section in schedule.sections:
            if section.name == ADDED_SECTION_NAME:
                continue
            else:
                for cat in section.categories:
                    for task in cat.tasks:
                        assignees = (
                            ", ".join(task.assignees) if task.assignees else ""
                        )
                        tasks_list.append(
                            {
                                "section": section.name,
                                "category": cat.name,
                                "task": task.title,
                                "assignees": assignees,
                            }
                        )
        # 추가된 일정: 프로그램팀 전체 멤버를 대상으로 표시
        for member in sorted(config.program_team_members):
            cat_name = f"{member}의 작업"
            tasks_list.append(
                {
                    "section": ADDED_SECTION_NAME,
                    "category": cat_name,
                    "task": cat_name,
                }
            )

        return jsonify({"tasks": tasks_list})

    @schedule_api.route("/schedule/move-issue", methods=["POST"])
    def api_move_issue():
        """이슈를 다른 작업으로 수동 이동한다."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "요청 데이터가 없습니다."}), 400

        issue_key = data.get("issue_key", "")
        target_category = data.get("target_category", "")
        target_task = data.get("target_task", "")

        if not issue_key or not target_category or not target_task:
            return jsonify({"error": "필수 항목이 누락되었습니다."}), 400

        page_id = get_setting_fn("confluence_sprint_page_id")
        if not page_id:
            return jsonify({"error": "페이지 ID가 설정되지 않았습니다."}), 503

        manual_match_store.set_override(
            page_id, issue_key, target_category, target_task
        )
        _refresh_cache_with_overrides()
        return jsonify({"ok": True})

    @schedule_api.route("/schedule/move-issue", methods=["DELETE"])
    def api_remove_move():
        """이슈의 수동 이동을 해제한다."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "요청 데이터가 없습니다."}), 400

        issue_key = data.get("issue_key", "")
        if not issue_key:
            return jsonify({"error": "issue_key가 필요합니다."}), 400

        page_id = get_setting_fn("confluence_sprint_page_id")
        if not page_id:
            return jsonify({"error": "페이지 ID가 설정되지 않았습니다."}), 503

        manual_match_store.remove_override(page_id, issue_key)
        _refresh_cache_with_overrides()
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    def _refresh_cache_with_overrides() -> None:
        """캐시된 스케줄에 수동 오버라이드를 재적용하여 즉시 갱신한다."""
        cached_data, _ = cache_store.get(_schedule_cache_key())
        if cached_data is None:
            return

        schedule = SprintSchedule.from_dict(cached_data)
        page_id = get_setting_fn("confluence_sprint_page_id")

        issue_map = _collect_issue_map_from_schedule(schedule)

        schedule.sections = [
            s for s in schedule.sections if s.name != ADDED_SECTION_NAME
        ]

        overrides = manual_match_store.get_overrides(page_id)
        if overrides:
            apply_manual_overrides(schedule, overrides, issue_map)

        from sprintlens.unmatched_issues import (
            build_unmatched_section,
            collect_matched_keys,
        )

        matched_keys = collect_matched_keys(schedule)
        all_issues = list(issue_map.values())
        unmatched_section = build_unmatched_section(all_issues, matched_keys)
        if unmatched_section:
            schedule.sections.append(unmatched_section)

        cache_store.set(_schedule_cache_key(), schedule.to_dict())

    def _collect_issue_map_from_schedule(
        schedule: SprintSchedule,
    ) -> dict[str, IssueInfo]:
        """캐시된 스케줄의 MatchedIssue에서 IssueInfo 맵을 추출한다."""
        issue_map: dict[str, IssueInfo] = {}
        for section in schedule.sections:
            for cat in section.categories:
                for task in cat.tasks:
                    assignee = task.assignees[0] if task.assignees else None
                    for mi in task.matched_issues:
                        issue_map[mi.key] = IssueInfo(
                            key=mi.key,
                            summary=mi.summary,
                            status=mi.status,
                            status_category=mi.status_category,
                            assignee=assignee,
                            icon_url=mi.icon_url,
                            parent_key=mi.parent_key,
                            parent_summary=mi.parent_summary,
                            resolved_date=mi.resolved_date,
                        )
        return issue_map

    def _build_schedule_cached(
        *, force_refresh: bool = False
    ) -> tuple[SprintSchedule | None, datetime | None]:
        """캐시를 활용하여 스프린트 일정을 반환한다."""
        cache_key = _schedule_cache_key()
        if not force_refresh:
            cached_data, updated_at = cache_store.get(cache_key)
            if cached_data is not None:
                return SprintSchedule.from_dict(cached_data), updated_at

        page_id = get_setting_fn("confluence_sprint_page_id")
        if force_refresh and page_id:
            match_store.delete(page_id)

        schedule = _build_schedule_fresh()
        if schedule is None:
            return None, None

        updated_at = cache_store.set(cache_key, schedule.to_dict())
        return schedule, updated_at

    def _build_schedule_fresh() -> SprintSchedule | None:
        """Confluence 일정을 가져와 파싱하고, Jira 이슈를 AI로 매칭한다."""
        page_id = get_setting_fn("confluence_sprint_page_id")
        members = get_setting_fn("program_team_members")
        team_members = (
            tuple(m.strip() for m in members.split(",") if m.strip())
            if members
            else config.program_team_members
        )
        return build_schedule(
            confluence_service=confluence_service,
            page_id=page_id,
            jira_service=jira_service,
            schedule_matcher=schedule_matcher,
            match_store=match_store,
            manual_match_store=manual_match_store,
            program_team_members=team_members,
        )
