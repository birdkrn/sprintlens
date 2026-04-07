"""SprintLens 설정 관리 모듈."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SidebarLink:
    """사이드바 외부 링크 항목."""

    name: str
    url: str
    icon: str = "link"  # "board", "doc", "link" 등


@dataclass(frozen=True)
class Config:
    """애플리케이션 설정."""

    # Logging
    log_level: str = "INFO"

    # Flask
    flask_host: str = "0.0.0.0"
    flask_port: int = 5000
    flask_debug: bool = False
    flask_secret_key: str = "change-me"

    # Data
    data_dir: str = ""

    # Cache
    cache_ttl_minutes: int = 60

    # Settings
    settings_password: str = ""

    # Jira
    jira_base_url: str = ""
    jira_username: str = ""
    jira_password: str = ""
    jira_board_id: str = ""
    jira_project_key: str = ""

    # QA_GMG Jira (기존 Jira 서버 공유, project_key만 다름)
    qa_gmg_jira_project_key: str = ""
    qa_gmg_jql_statuses: tuple[str, ...] = (
        "NEW ISSUE",
        "ASSIGNED ISSUE",
        "IN PROGRESS",
        "IN PROGRESS(HOLD)",
    )

    # QA_GMG 팀 멤버
    qa_gmg_dev_members: tuple[str, ...] = ()  # 개발팀 멤버 (이 외는 라인으로 분류)
    qa_gmg_new_issue_days: int = 3  # 신규 이슈 판별 기준 일수

    # Confluence
    confluence_base_url: str = ""
    confluence_username: str = ""
    confluence_password: str = ""
    confluence_space_key: str = ""
    confluence_sprint_page_id: str = ""

    # 프로그램팀 멤버
    program_team_members: tuple[str, ...] = ()

    # Gemini AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Sidebar 외부 링크
    sidebar_links: tuple[SidebarLink, ...] = ()

    # Slack
    slack_webhook_url: str = ""
    slack_report_time: str = "09:00"
    slack_report_enabled: bool = False
    slack_dashboard_url: str = ""
    slack_show_in_progress: int = 99
    slack_show_done: int = 5
    slack_show_waiting: int = 5
    slack_show_added: int = 5

    def validate(self) -> list[str]:
        """전체 필수 설정값 검증. 누락된 항목 목록을 반환한다."""
        return self.validate_jira() + self.validate_confluence()

    def validate_jira(self) -> list[str]:
        """Jira 관련 필수 설정값 검증."""
        errors: list[str] = []
        if not self.jira_base_url:
            errors.append("JIRA_BASE_URL")
        if not self.jira_username:
            errors.append("JIRA_USERNAME")
        if not self.jira_password:
            errors.append("JIRA_PASSWORD")
        if not self.jira_board_id:
            errors.append("JIRA_BOARD_ID")
        if not self.jira_project_key:
            errors.append("JIRA_PROJECT_KEY")
        return errors

    def validate_qa_gmg_jira(self) -> list[str]:
        """QA_GMG Jira 관련 필수 설정값 검증."""
        errors: list[str] = []
        if not self.qa_gmg_jira_project_key:
            errors.append("QA_GMG_JIRA_PROJECT_KEY")
        return errors

    def validate_confluence(self) -> list[str]:
        """Confluence 관련 필수 설정값 검증."""
        errors: list[str] = []
        if not self.confluence_base_url:
            errors.append("CONFLUENCE_BASE_URL")
        if not self.confluence_username:
            errors.append("CONFLUENCE_USERNAME")
        if not self.confluence_password:
            errors.append("CONFLUENCE_PASSWORD")
        if not self.confluence_space_key:
            errors.append("CONFLUENCE_SPACE_KEY")
        if not self.confluence_sprint_page_id:
            errors.append("CONFLUENCE_SPRINT_PAGE_ID")
        return errors

    def validate_slack(self) -> list[str]:
        """슬랙 리포트 관련 설정값 검증."""
        errors: list[str] = []
        if not self.slack_webhook_url:
            errors.append("SLACK_WEBHOOK_URL")
        return errors


_SIDEBAR_LINKS_FILE = Path(__file__).resolve().parent.parent / "sidebar_links.json"


def _parse_sidebar_links(raw: str) -> tuple[SidebarLink, ...]:
    """사이드바 링크를 로드한다.

    우선순위: SIDEBAR_LINKS 환경변수 → sidebar_links.json 파일.
    """
    if not raw and _SIDEBAR_LINKS_FILE.is_file():
        raw = _SIDEBAR_LINKS_FILE.read_text(encoding="utf-8")
    if not raw:
        return ()
    try:
        items = json.loads(raw)
        return tuple(
            SidebarLink(
                name=item["name"],
                url=item["url"],
                icon=item.get("icon", "link"),
            )
            for item in items
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("SIDEBAR_LINKS 파싱 실패: %s", raw)
        return ()


def load_config() -> Config:
    """환경 변수에서 설정을 로드한다.

    SPRINTLENS_ENV=dev 이면 .env.dev → .env 순서로 로드하여
    개발용 설정이 우선 적용된다.
    """
    env_file = Path(__file__).resolve().parent.parent

    if os.getenv("SPRINTLENS_ENV") == "dev":
        load_dotenv(env_file / ".env.dev")
        logger.info("개발 환경 설정 로드: .env.dev")

    load_dotenv(env_file / ".env")

    return Config(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
        flask_port=int(os.getenv("FLASK_PORT", "5000")),
        flask_debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        flask_secret_key=os.getenv("FLASK_SECRET_KEY", "change-me"),
        data_dir=os.getenv(
            "DATA_DIR",
            str(Path(__file__).resolve().parent.parent / "data"),
        ),
        cache_ttl_minutes=int(os.getenv("CACHE_TTL_MINUTES", "60")),
        settings_password=os.getenv("SETTINGS_PASSWORD", ""),
        jira_base_url=os.getenv("JIRA_BASE_URL", ""),
        jira_username=os.getenv("JIRA_USERNAME", ""),
        jira_password=os.getenv("JIRA_PASSWORD", ""),
        jira_board_id=os.getenv("JIRA_BOARD_ID", ""),
        jira_project_key=os.getenv("JIRA_PROJECT_KEY", ""),
        qa_gmg_jira_project_key=os.getenv("QA_GMG_JIRA_PROJECT_KEY", ""),
        qa_gmg_jql_statuses=tuple(
            s.strip()
            for s in os.getenv(
                "QA_GMG_JQL_STATUSES",
                "NEW ISSUE,ASSIGNED ISSUE,IN PROGRESS,IN PROGRESS(HOLD)",
            ).split(",")
            if s.strip()
        ),
        qa_gmg_dev_members=tuple(
            name.strip()
            for name in os.getenv("QA_GMG_DEV_MEMBERS", "").split(",")
            if name.strip()
        ),
        qa_gmg_new_issue_days=int(os.getenv("QA_GMG_NEW_ISSUE_DAYS", "3")),
        confluence_base_url=os.getenv("CONFLUENCE_BASE_URL", ""),
        confluence_username=os.getenv("CONFLUENCE_USERNAME", ""),
        confluence_password=os.getenv("CONFLUENCE_PASSWORD", ""),
        confluence_space_key=os.getenv("CONFLUENCE_SPACE_KEY", ""),
        confluence_sprint_page_id=os.getenv("CONFLUENCE_SPRINT_PAGE_ID", ""),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
        slack_report_time=os.getenv("SLACK_REPORT_TIME", "09:00"),
        slack_dashboard_url=os.getenv("SLACK_DASHBOARD_URL", ""),
        slack_show_in_progress=int(os.getenv("SLACK_SHOW_IN_PROGRESS", "99")),
        slack_show_done=int(os.getenv("SLACK_SHOW_DONE", "5")),
        slack_show_waiting=int(os.getenv("SLACK_SHOW_WAITING", "5")),
        slack_show_added=int(os.getenv("SLACK_SHOW_ADDED", "5")),
        program_team_members=tuple(
            name.strip()
            for name in os.getenv("PROGRAM_TEAM_MEMBERS", "").split(",")
            if name.strip()
        ),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        sidebar_links=_parse_sidebar_links(
            os.getenv("SIDEBAR_LINKS", "")
        ),
        slack_report_enabled=os.getenv("SLACK_REPORT_ENABLED", "false").lower()
        == "true",
    )
