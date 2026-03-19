"""SprintLens - 스프린트 진행상황 리포트 웹 서비스."""

from dataclasses import dataclass

from flask import Flask, render_template, request

from sprintlens.config import load_config
from sprintlens.confluence_service import ConfluenceService
from sprintlens.jira_service import JiraService
from sprintlens.logging_config import get_logger, setup_logging
from sprintlens.report_service import ReportService
from sprintlens.scheduler import ReportScheduler
from sprintlens.slack_service import SlackService

logger = get_logger(__name__)


def create_app() -> Flask:
    """Flask 애플리케이션 팩토리."""
    config = load_config()
    setup_logging(config.log_level)

    app = Flask(__name__)
    app.secret_key = config.flask_secret_key

    # 서비스 초기화 (설정이 유효한 경우에만)
    jira_service: JiraService | None = None
    confluence_service: ConfluenceService | None = None
    report_service: ReportService | None = None

    jira_errors = config.validate_jira()
    if jira_errors:
        logger.warning("Jira 설정 누락: %s", ", ".join(jira_errors))
    else:
        jira_service = JiraService(
            base_url=config.jira_base_url,
            username=config.jira_username,
            password=config.jira_password,
            board_id=config.jira_board_id,
        )
        report_service = ReportService(jira_service=jira_service)

    confluence_errors = config.validate_confluence()
    if confluence_errors:
        logger.warning(
            "Confluence 설정 누락: %s", ", ".join(confluence_errors)
        )
    else:
        confluence_service = ConfluenceService(
            base_url=config.confluence_base_url,
            username=config.confluence_username,
            api_token=config.confluence_api_token,
        )

    # 슬랙 스케줄러 (활성화된 경우)
    scheduler: ReportScheduler | None = None
    if config.slack_report_enabled and report_service:
        slack_errors = config.validate_slack()
        if slack_errors:
            logger.error("슬랙 설정 누락: %s", ", ".join(slack_errors))
        else:
            slack_service = SlackService(
                bot_token=config.slack_bot_token,
                channel_id=config.slack_channel_id,
            )
            scheduler = ReportScheduler(
                report_service=report_service,
                slack_service=slack_service,
                report_time=config.slack_report_time,
            )
            scheduler.start()

    # 서비스를 app에 저장하여 라우트에서 사용
    app.config["report_service"] = report_service
    app.config["confluence_service"] = confluence_service
    app.config["app_config"] = config

    # ------------------------------------------------------------------
    # 메뉴 시스템
    # ------------------------------------------------------------------

    @dataclass
    class MenuItem:
        """네비게이션 메뉴 항목."""

        id: str
        label: str
        url: str
        partial_url: str

    menu_items = [
        MenuItem(
            id="dashboard",
            label="대시보드",
            url="/",
            partial_url="/partials/dashboard",
        ),
    ]

    @app.context_processor
    def inject_menu():
        """모든 템플릿에 메뉴 데이터를 주입한다."""
        active = "dashboard"
        for item in menu_items:
            if request.path == item.url:
                active = item.id
                break

        active_item = next(
            (m for m in menu_items if m.id == active), menu_items[0]
        )
        return {
            "menu_items": menu_items,
            "active_menu": active,
            "current_partial_url": active_item.partial_url,
        }

    # ------------------------------------------------------------------
    # 라우트
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        """스프린트 리포트 메인 페이지."""
        report = None
        schedule = None

        if report_service:
            try:
                report = report_service.generate_sprint_report()
            except Exception:
                logger.exception("스프린트 리포트 생성 실패")

        if confluence_service and config.confluence_sprint_page_id:
            try:
                schedule = confluence_service.get_sprint_schedule(
                    config.confluence_sprint_page_id
                )
            except Exception:
                logger.exception("컨플루언스 일정 조회 실패")

        return render_template(
            "index.html",
            report=report,
            schedule=schedule,
            config=config,
        )

    @app.route("/partials/dashboard")
    def partials_dashboard():
        """HTMX 파셜: 대시보드 콘텐츠."""
        report = None
        schedule = None

        if report_service:
            try:
                report = report_service.generate_sprint_report()
            except Exception:
                logger.exception("스프린트 리포트 생성 실패")

        if confluence_service and config.confluence_sprint_page_id:
            try:
                schedule = confluence_service.get_sprint_schedule(
                    config.confluence_sprint_page_id
                )
            except Exception:
                logger.exception("컨플루언스 일정 조회 실패")

        return render_template(
            "partials/dashboard.html",
            report=report,
            schedule=schedule,
            config=config,
        )

    @app.route("/api/report")
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

    return app


if __name__ == "__main__":
    config = load_config()
    app = create_app()
    app.run(
        host=config.flask_host,
        port=config.flask_port,
        debug=config.flask_debug,
    )
