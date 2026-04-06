"""Flask 라우트 정의 모듈."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from sprintlens.logging_config import get_logger
from sprintlens.routes_qa_gmg import (
    init_qa_gmg_routes,
    qa_gmg_api,
    qa_gmg_pages,
)
from sprintlens.routes_schedule import (
    init_schedule_routes,
    schedule_api,
    schedule_pages,
)

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
            k: str(v).strip() for k, v in data.items() if k in settings_keys
        }
        if to_save:
            settings_store.set_many(to_save)
            cache_key = f"schedule:{_get_setting('confluence_sprint_page_id')}"
            cache_store.invalidate(cache_key)

        return jsonify({"ok": True, "saved": list(to_save.keys())})

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
    # 헬퍼
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 서브 모듈 라우트 초기화
    # ------------------------------------------------------------------
    init_schedule_routes(
        config=config,
        confluence_service=confluence_service,
        jira_service=jira_service,
        schedule_matcher=schedule_matcher,
        cache_store=cache_store,
        settings_store=settings_store,
        match_store=match_store,
        manual_match_store=manual_match_store,
        slack_service=slack_service,
        schedule_builder=schedule_builder,
        get_setting_fn=_get_setting,
    )

    init_qa_gmg_routes(
        config=config,
        qa_gmg_report_service=qa_gmg_report_service,
        starred_store=starred_store,
        get_setting_fn=_get_setting,
    )

    # Blueprint 등록
    app.register_blueprint(pages)
    app.register_blueprint(api)
    app.register_blueprint(schedule_pages)
    app.register_blueprint(schedule_api)
    app.register_blueprint(qa_gmg_pages)
    app.register_blueprint(qa_gmg_api)
