"""Flask 라우트 정의 모듈."""

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

pages = Blueprint("pages", __name__)
api = Blueprint("api", __name__, url_prefix="/api")


def init_routes(
    app,
    *,
    config,
    report_service,
    confluence_service,
    jira_service,
    schedule_matcher,
    cache_store,
    settings_store,
    match_store,
    manual_match_store,
    settings_keys: list[str],
    slack_service=None,
    schedule_builder=None,
    qa_gmg_report_service=None,
    starred_store=None,
) -> None:
    """라우트를 Flask 앱에 등록한다."""

    def _get_setting(key: str) -> str:
        """DB 설정값을 우선 사용하고, 없으면 config 폴백."""
        db_val = settings_store.get(key)
        if db_val:
            return db_val
        env_val = getattr(config, key, "")
        if isinstance(env_val, tuple):
            return ",".join(env_val)
        return str(env_val)

    def _schedule_cache_key() -> str:
        return f"schedule:{_get_setting('confluence_sprint_page_id')}"

    # ------------------------------------------------------------------
    # 페이지 라우트
    # ------------------------------------------------------------------

    @pages.route("/")
    def index():
        """홈 페이지."""
        return render_template(
            "index.html",
            active_partial="partials/home.html",
            config=config,
        )

    @pages.route("/dashboard")
    def dashboard():
        """대시보드 페이지 (로딩 화면 먼저 표시)."""
        return render_template(
            "index.html",
            active_partial="partials/dashboard_loading.html",
            config=config,
        )

    @pages.route("/schedule")
    def schedule():
        """프로그램팀 일정 페이지 (로딩 화면 먼저 표시)."""
        return render_template(
            "index.html",
            active_partial="partials/schedule_loading.html",
            config=config,
        )

    @pages.route("/qa-gmg")
    def qa_gmg():
        """QA_GMG 대시보드 페이지 (로딩 화면 먼저 표시)."""
        return render_template(
            "index.html",
            active_partial="partials/qa_gmg_loading.html",
            config=config,
        )

    @pages.route("/settings")
    def settings_page():
        """설정 페이지."""
        return render_template(
            "index.html",
            active_partial="partials/settings.html",
            settings=_get_effective_settings(),
            config=config,
        )

    # ------------------------------------------------------------------
    # HTMX 파셜 라우트
    # ------------------------------------------------------------------

    @pages.route("/partials/home")
    def partials_home():
        """HTMX 파셜: 홈."""
        return render_template("partials/home.html", config=config)

    @pages.route("/partials/dashboard")
    def partials_dashboard():
        """HTMX 파셜: 대시보드 (로딩 화면)."""
        return render_template("partials/dashboard_loading.html", config=config)

    @pages.route("/partials/dashboard/data")
    def partials_dashboard_data():
        """HTMX 파셜: 대시보드 데이터 (비동기 로드)."""
        report = _build_dashboard_report()
        return render_template(
            "partials/dashboard.html",
            report=report,
            jira_base_url=config.jira_base_url,
            config=config,
        )

    @pages.route("/partials/schedule")
    def partials_schedule():
        """HTMX 파셜: 프로그램팀 일정 (로딩 화면)."""
        refresh = request.args.get("refresh") == "1"
        return render_template(
            "partials/schedule_loading.html",
            refresh=refresh,
            config=config,
        )

    @pages.route("/partials/schedule/data")
    def partials_schedule_data():
        """HTMX 파셜: 프로그램팀 일정 데이터 (비동기 로드)."""
        refresh = request.args.get("refresh") == "1"
        sprint_schedule, updated_at = _build_schedule_cached(force_refresh=refresh)
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

    @pages.route("/partials/qa-gmg")
    def partials_qa_gmg():
        """HTMX 파셜: QA_GMG 대시보드 (로딩 화면)."""
        return render_template("partials/qa_gmg_loading.html", config=config)

    @pages.route("/partials/qa-gmg/data")
    def partials_qa_gmg_data():
        """HTMX 파셜: QA_GMG 대시보드 데이터 (비동기 로드)."""
        report = _build_qa_gmg_report()
        starred_keys = starred_store.get_all() if starred_store else set()
        return render_template(
            "partials/qa_gmg_dashboard.html",
            report=report,
            jira_base_url=config.jira_base_url,
            starred_keys=starred_keys,
            config=config,
        )

    @pages.route("/partials/settings")
    def partials_settings():
        """HTMX 파셜: 설정 화면."""
        return render_template(
            "partials/settings.html",
            settings=_get_effective_settings(),
            config=config,
        )

    # ------------------------------------------------------------------
    # API 라우트
    # ------------------------------------------------------------------

    @api.route("/settings", methods=["POST"])
    def api_save_settings():
        """설정 저장 API."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "요청 데이터가 없습니다."}), 400

        password = data.pop("password", "")
        if password != config.settings_password:
            return jsonify({"error": "비밀번호가 일치하지 않습니다."}), 403

        to_save = {k: str(v).strip() for k, v in data.items() if k in settings_keys}
        if to_save:
            settings_store.set_many(to_save)
            cache_store.invalidate(_schedule_cache_key())

        return jsonify({"ok": True, "saved": list(to_save.keys())})

    @api.route("/slack/test", methods=["POST"])
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

    @api.route("/qa-gmg/star", methods=["POST"])
    def api_toggle_star():
        """QA_GMG 이슈 별표를 토글한다."""
        if not starred_store:
            return jsonify({"error": "별표 저장소가 초기화되지 않았습니다."}), 503
        data = request.get_json()
        if not data or not data.get("issue_key"):
            return jsonify({"error": "issue_key가 필요합니다."}), 400
        starred = starred_store.toggle(data["issue_key"])
        return jsonify({"ok": True, "starred": starred})

    @api.route("/report")
    def api_report():
        """스프린트 리포트 JSON API."""
        if not report_service:
            return {"error": "Jira 설정이 되어 있지 않습니다."}, 503

        report = report_service.generate_sprint_report()
        if not report:
            return {"error": "활성 스프린트가 없습니다."}, 404

        return {
            "sprint": {
                "name": report.sprint.name,
                "state": report.sprint.state,
                "start_date": report.sprint.start_date,
                "end_date": report.sprint.end_date,
            },
            "progress": {
                "total": report.total_issues,
                "done": report.done_count,
                "percent": round(report.progress_percent, 1),
            },
            "by_assignee": [
                {
                    "name": ar.name,
                    "total": ar.total,
                    "done": ar.done_count,
                    "in_progress": ar.in_progress_count,
                    "todo": ar.todo_count,
                }
                for ar in report.by_assignee
            ],
            "by_story": [
                {
                    "story_key": sr.story_key,
                    "story_summary": sr.story_summary,
                    "total": sr.total,
                    "done": sr.done_count,
                }
                for sr in report.by_story
            ],
        }

    @api.route("/schedule/tasks")
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
                        assignees = ", ".join(task.assignees) if task.assignees else ""
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

    @api.route("/schedule/move-issue", methods=["POST"])
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

        page_id = _get_setting("confluence_sprint_page_id")
        if not page_id:
            return jsonify({"error": "페이지 ID가 설정되지 않았습니다."}), 503

        manual_match_store.set_override(
            page_id, issue_key, target_category, target_task
        )
        # 캐시된 스케줄에 오버라이드만 적용하여 즉시 갱신 (전체 리빌드 방지)
        _refresh_cache_with_overrides()
        return jsonify({"ok": True})

    @api.route("/schedule/move-issue", methods=["DELETE"])
    def api_remove_move():
        """이슈의 수동 이동을 해제한다."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "요청 데이터가 없습니다."}), 400

        issue_key = data.get("issue_key", "")
        if not issue_key:
            return jsonify({"error": "issue_key가 필요합니다."}), 400

        page_id = _get_setting("confluence_sprint_page_id")
        if not page_id:
            return jsonify({"error": "페이지 ID가 설정되지 않았습니다."}), 503

        manual_match_store.remove_override(page_id, issue_key)
        _refresh_cache_with_overrides()
        return jsonify({"ok": True})

    def _refresh_cache_with_overrides() -> None:
        """캐시된 스케줄에 수동 오버라이드를 재적용하여 즉시 갱신한다.

        전체 리빌드(Confluence/Jira/Gemini API 호출) 없이
        캐시된 데이터에 오버라이드만 반영하여 빠르게 갱신한다.
        """
        cached_data, _ = cache_store.get(_schedule_cache_key())
        if cached_data is None:
            return

        schedule = SprintSchedule.from_dict(cached_data)
        page_id = _get_setting("confluence_sprint_page_id")

        # 이슈 정보 수집 (추가된 일정 포함, 삭제 전에 수집)
        issue_map = _collect_issue_map_from_schedule(schedule)

        # 기존 "추가된 일정" 섹션 제거 (재생성할 것이므로)
        schedule.sections = [
            s for s in schedule.sections if s.name != ADDED_SECTION_NAME
        ]

        # 수동 오버라이드 적용
        overrides = manual_match_store.get_overrides(page_id)
        if overrides:
            apply_manual_overrides(schedule, overrides, issue_map)

        # "추가된 일정" 섹션 재생성
        from sprintlens.unmatched_issues import (
            build_unmatched_section,
            collect_matched_keys,
        )

        matched_keys = collect_matched_keys(schedule)
        all_issues = list(issue_map.values())
        unmatched_section = build_unmatched_section(all_issues, matched_keys)
        if unmatched_section:
            schedule.sections.append(unmatched_section)

        # 캐시 재저장
        cache_store.set(_schedule_cache_key(), schedule.to_dict())

    def _collect_issue_map_from_schedule(
        schedule: SprintSchedule,
    ) -> dict[str, IssueInfo]:
        """캐시된 스케줄의 MatchedIssue에서 IssueInfo 맵을 추출한다."""
        issue_map: dict[str, IssueInfo] = {}
        for section in schedule.sections:
            for cat in section.categories:
                for task in cat.tasks:
                    # task의 담당자 정보를 이슈에 반영
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

    # ------------------------------------------------------------------
    # 헬퍼 (라우트에서 사용)
    # ------------------------------------------------------------------

    def _build_schedule_cached(
        *, force_refresh: bool = False
    ) -> tuple[SprintSchedule | None, datetime | None]:
        """캐시를 활용하여 스프린트 일정을 반환한다."""
        cache_key = _schedule_cache_key()
        if not force_refresh:
            cached_data, updated_at = cache_store.get(cache_key)
            if cached_data is not None:
                return SprintSchedule.from_dict(cached_data), updated_at

        # 강제 새로고침 시 저장된 매칭도 삭제하여 Gemini 재매칭 유도
        page_id = _get_setting("confluence_sprint_page_id")
        if force_refresh and page_id:
            match_store.delete(page_id)

        schedule = _build_schedule_fresh()
        if schedule is None:
            return None, None

        updated_at = cache_store.set(cache_key, schedule.to_dict())
        return schedule, updated_at

    def _build_schedule_fresh() -> SprintSchedule | None:
        """Confluence 일정을 가져와 파싱하고, Jira 이슈를 AI로 매칭한다."""
        page_id = _get_setting("confluence_sprint_page_id")
        members = _get_setting("program_team_members")
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

    def _build_dashboard_report():
        """대시보드용 스프린트 리포트를 생성한다."""
        if not report_service:
            return None
        try:
            return report_service.generate_sprint_report()
        except Exception:
            logger.exception("스프린트 리포트 생성 실패")
            return None

    def _build_qa_gmg_report():
        """QA_GMG 대시보드용 프로젝트 리포트를 생성한다."""
        if not qa_gmg_report_service:
            return None
        try:
            # settings_store에서 먼저 조회, 없으면 config 폴백
            dev_members_str = _get_setting("qa_gmg_dev_members")
            dev_members = (
                tuple(m.strip() for m in dev_members_str.split(",") if m.strip())
                if dev_members_str
                else config.qa_gmg_dev_members
            )
            return qa_gmg_report_service.generate_project_report(
                config.qa_gmg_jira_project_key,
                statuses=config.qa_gmg_jql_statuses,
                dev_members=dev_members,
            )
        except Exception:
            logger.exception("QA_GMG 프로젝트 리포트 생성 실패")
            return None

    def _get_effective_settings() -> dict[str, str]:
        """DB 설정 → .env 폴백 순으로 유효한 설정값을 반환한다."""
        db_settings = settings_store.get_all()
        result: dict[str, str] = {}
        for key in settings_keys:
            db_val = db_settings.get(key, "")
            if db_val:
                result[key] = db_val
            else:
                env_val = getattr(config, key, "")
                if isinstance(env_val, tuple):
                    env_val = ",".join(env_val)
                result[key] = str(env_val)
        return result

    # Blueprint 등록
    app.register_blueprint(pages)
    app.register_blueprint(api)
