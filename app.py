"""SprintLens - 스프린트 진행상황 리포트 웹 서비스."""

import os
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, request

from sprintlens.cache_store import CacheStore
from sprintlens.config import load_config
from sprintlens.confluence_service import ConfluenceService
from sprintlens.gemini_service import GeminiService
from sprintlens.jira_service import JiraService
from sprintlens.logging_config import get_logger, setup_logging
from sprintlens.manual_match_store import ManualMatchStore
from sprintlens.match_store import MatchStore
from sprintlens.prompt_loader import PromptLoader
from sprintlens.report_service import ReportService
from sprintlens.routes import init_routes
from sprintlens.schedule_builder import build_schedule
from sprintlens.schedule_matcher import ScheduleMatcher
from sprintlens.scheduler import ReportScheduler
from sprintlens.settings_store import SettingsStore
from sprintlens.slack_service import SlackService
from sprintlens.starred_store import StarredIssueStore

logger = get_logger(__name__)

# 웹 설정에서 변경 가능한 항목 목록
SETTINGS_KEYS = [
    "confluence_sprint_page_id",
    "program_team_members",
    "jira_base_url",
    "jira_board_id",
    "jira_project_key",
    "confluence_base_url",
    "confluence_space_key",
    "qa_gmg_dev_members",
]


def create_app() -> Flask:
    """Flask 애플리케이션 팩토리."""
    config = load_config()
    setup_logging(config.log_level)

    app = Flask(__name__)
    app.secret_key = config.flask_secret_key

    # ------------------------------------------------------------------
    # 서비스 초기화
    # ------------------------------------------------------------------
    jira_service = _init_jira(config)
    report_service = ReportService(jira_service=jira_service) if jira_service else None
    qa_gmg_jira_service = _init_qa_gmg_jira(config)
    qa_gmg_report_service = ReportService(jira_service=qa_gmg_jira_service) if qa_gmg_jira_service else None
    confluence_service = _init_confluence(config)
    schedule_matcher = _init_gemini_matcher(config)

    # 저장소
    data_dir = Path(config.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_store = CacheStore(
        db_path=data_dir / "cache.db",
        ttl_minutes=config.cache_ttl_minutes,
    )
    settings_store = SettingsStore(db_path=data_dir / "settings.db")
    match_store = MatchStore(db_path=data_dir / "matches.db")
    manual_match_store = ManualMatchStore(
        db_path=data_dir / "manual_matches.db"
    )
    starred_store = StarredIssueStore(db_path=data_dir / "starred.db")

    # 슬랙 스케줄러용 일정 빌더
    def _build_schedule_for_slack():
        """슬랙 리포트용 스프린트 일정을 빌드한다."""
        return build_schedule(
            confluence_service=confluence_service,
            page_id=config.confluence_sprint_page_id,
            jira_service=jira_service,
            schedule_matcher=schedule_matcher,
            match_store=match_store,
            manual_match_store=manual_match_store,
            program_team_members=config.program_team_members,
        )

    _init_slack_scheduler(config, _build_schedule_for_slack)

    # ------------------------------------------------------------------
    # 메뉴 시스템
    # ------------------------------------------------------------------

    @dataclass
    class MenuItem:
        """네비게이션 메뉴 항목."""

        id: str
        label: str
        description: str
        url: str
        partial_url: str

    all_menu_items = [
        MenuItem(
            id="dashboard",
            label="대시보드",
            description="스프린트 현황 및 일감 진행률",
            url="/dashboard",
            partial_url="/partials/dashboard",
        ),
        MenuItem(
            id="schedule",
            label="프로그램팀 대시보드",
            description="프로그램팀 스프린트 일정 및 진행 현황",
            url="/schedule",
            partial_url="/partials/schedule",
        ),
        MenuItem(
            id="qa_gmg",
            label="QA_GMG 대시보드",
            description="QA_GMG 스프린트 현황 및 일감 진행률",
            url="/qa-gmg",
            partial_url="/partials/qa-gmg",
        ),
    ]

    # .env의 MENU_{ID}_ENABLED로 메뉴 노출 제어 (기본값: true)
    menu_items = [
        m
        for m in all_menu_items
        if os.getenv(f"MENU_{m.id.upper()}_ENABLED", "true").lower()
        == "true"
    ]
    url_to_menu: dict[str, str] = {m.url: m.id for m in menu_items}

    @app.context_processor
    def inject_menu():
        """모든 템플릿에 메뉴 데이터를 주입한다."""
        active = url_to_menu.get(request.path, "")
        return {"menu_items": menu_items, "active_menu": active}

    # ------------------------------------------------------------------
    # 라우트 등록
    # ------------------------------------------------------------------
    # Slack 서비스 (테스트 발송용)
    slack_svc = None
    if config.slack_webhook_url:
        slack_svc = SlackService(webhook_url=config.slack_webhook_url)

    init_routes(
        app,
        config=config,
        report_service=report_service,
        confluence_service=confluence_service,
        jira_service=jira_service,
        schedule_matcher=schedule_matcher,
        cache_store=cache_store,
        settings_store=settings_store,
        match_store=match_store,
        manual_match_store=manual_match_store,
        settings_keys=SETTINGS_KEYS,
        slack_service=slack_svc,
        schedule_builder=_build_schedule_for_slack,
        qa_gmg_report_service=qa_gmg_report_service,
        starred_store=starred_store,
    )

    return app


# ------------------------------------------------------------------
# 서비스 초기화 헬퍼
# ------------------------------------------------------------------


def _init_jira(config) -> JiraService | None:
    """Jira 서비스를 초기화한다."""
    errors = config.validate_jira()
    if errors:
        logger.warning("Jira 설정 누락: %s", ", ".join(errors))
        return None
    return JiraService(
        base_url=config.jira_base_url,
        username=config.jira_username,
        password=config.jira_password,
        board_id=config.jira_board_id,
    )


def _init_qa_gmg_jira(config) -> JiraService | None:
    """QA_GMG Jira 서비스를 초기화한다.

    QA_GMG는 스프린트 보드 없이 JQL로 이슈를 조회하므로
    board_id 없이 기존 Jira 서버 인증만 공유한다.
    """
    errors = config.validate_qa_gmg_jira()
    if errors:
        logger.warning("QA_GMG Jira 설정 누락: %s", ", ".join(errors))
        return None
    # 기존 Jira 서버 인증 정보 공유
    jira_errors = []
    if not config.jira_base_url:
        jira_errors.append("JIRA_BASE_URL")
    if not config.jira_username:
        jira_errors.append("JIRA_USERNAME")
    if not config.jira_password:
        jira_errors.append("JIRA_PASSWORD")
    if jira_errors:
        logger.warning("Jira 공통 설정 누락: %s", ", ".join(jira_errors))
        return None
    return JiraService(
        base_url=config.jira_base_url,
        username=config.jira_username,
        password=config.jira_password,
    )


def _init_confluence(config) -> ConfluenceService | None:
    """Confluence 서비스를 초기화한다."""
    errors = config.validate_confluence()
    if errors:
        logger.warning("Confluence 설정 누락: %s", ", ".join(errors))
        return None
    return ConfluenceService(
        base_url=config.confluence_base_url,
        username=config.confluence_username,
        password=config.confluence_password,
    )


def _init_gemini_matcher(config) -> ScheduleMatcher | None:
    """Gemini AI + ScheduleMatcher를 초기화한다."""
    if not config.gemini_api_key:
        logger.warning("Gemini API 키 미설정: AI 매칭 비활성화")
        return None
    gemini_service = GeminiService(
        api_key=config.gemini_api_key,
        model=config.gemini_model,
    )
    prompts_dir = Path(__file__).resolve().parent / "prompts"
    prompt_loader = PromptLoader(prompts_dir)
    return ScheduleMatcher(
        gemini_service=gemini_service,
        prompt_loader=prompt_loader,
    )


def _init_slack_scheduler(config, schedule_builder) -> None:
    """슬랙 스케줄러를 초기화한다."""
    if not config.slack_report_enabled:
        return
    errors = config.validate_slack()
    if errors:
        logger.error("슬랙 설정 누락: %s", ", ".join(errors))
        return
    slack_service = SlackService(webhook_url=config.slack_webhook_url)
    scheduler = ReportScheduler(
        slack_service=slack_service,
        schedule_builder=schedule_builder,
        report_time=config.slack_report_time,
        dashboard_url=config.slack_dashboard_url,
        show_in_progress=config.slack_show_in_progress,
        show_done=config.slack_show_done,
        show_waiting=config.slack_show_waiting,
        show_added=config.slack_show_added,
    )
    scheduler.start()


if __name__ == "__main__":
    config = load_config()
    app = create_app()
    app.run(
        host=config.flask_host,
        port=config.flask_port,
        debug=config.flask_debug,
    )
