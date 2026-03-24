"""Flask 라우트 정의 모듈."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from sprintlens.burndown import calculate_burndown
from sprintlens.logging_config import get_logger
from sprintlens.schedule_parser import SprintSchedule, parse_schedule_html
from sprintlens.slack_report_formatter import format_slack_report

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
    settings_keys: list[str],
    slack_service=None,
    schedule_builder=None,
) -> None:
    """라우트를 Flask 앱에 등록한다."""

    schedule_cache_key = (
        f"schedule:{config.confluence_sprint_page_id}"
    )

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
        return render_template(
            "partials/dashboard_loading.html", config=config
        )

    @pages.route("/partials/dashboard/data")
    def partials_dashboard_data():
        """HTMX 파셜: 대시보드 데이터 (비동기 로드)."""
        report = _build_dashboard_report()
        return render_template(
            "partials/dashboard.html",
            report=report,
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

        to_save = {
            k: str(v).strip()
            for k, v in data.items()
            if k in settings_keys
        }
        if to_save:
            settings_store.set_many(to_save)
            cache_store.invalidate(schedule_cache_key)

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
        )
        success = slack_service.send_message(text)
        if success:
            return jsonify({"ok": True, "message": "슬랙 발송 완료"})
        return jsonify({"error": "슬랙 발송 실패"}), 500

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

    # ------------------------------------------------------------------
    # 헬퍼 (라우트에서 사용)
    # ------------------------------------------------------------------

    def _build_schedule_cached(
        *, force_refresh: bool = False
    ) -> tuple[SprintSchedule | None, datetime | None]:
        """캐시를 활용하여 스프린트 일정을 반환한다."""
        if not force_refresh:
            cached_data, updated_at = cache_store.get(schedule_cache_key)
            if cached_data is not None:
                return SprintSchedule.from_dict(cached_data), updated_at

        # 강제 새로고침 시 저장된 매칭도 삭제하여 Gemini 재매칭 유도
        if force_refresh and config.confluence_sprint_page_id:
            match_store.delete(config.confluence_sprint_page_id)

        schedule = _build_schedule_fresh()
        if schedule is None:
            return None, None

        updated_at = cache_store.set(
            schedule_cache_key, schedule.to_dict()
        )
        return schedule, updated_at

    def _build_schedule_fresh() -> SprintSchedule | None:
        """Confluence 일정을 가져와 파싱하고, Jira 이슈를 AI로 매칭한다."""
        if not confluence_service or not config.confluence_sprint_page_id:
            return None
        try:
            page = confluence_service.get_page(
                config.confluence_sprint_page_id
            )
            schedule = parse_schedule_html(page.title, page.body_html)

            if schedule_matcher and jira_service:
                sprint = jira_service.get_active_sprint()
                if sprint:
                    issues = jira_service.get_sprint_issues(
                        sprint.id, expand_changelog=True
                    )
                    if config.program_team_members:
                        members = set(config.program_team_members)
                        issues = [
                            i for i in issues if i.assignee in members
                        ]
                    schedule_matcher.match(
                        schedule,
                        issues,
                        match_store=match_store,
                        page_id=config.confluence_sprint_page_id,
                    )

            return schedule
        except Exception:
            logger.exception("스프린트 일정 조회 실패")
            return None

    def _build_dashboard_report():
        """대시보드용 스프린트 리포트를 생성한다."""
        if not report_service:
            return None
        try:
            return report_service.generate_sprint_report()
        except Exception:
            logger.exception("스프린트 리포트 생성 실패")
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
