"""SprintLens 설정 관리 모듈."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


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

    # Jira
    jira_base_url: str = ""
    jira_username: str = ""
    jira_password: str = ""
    jira_board_id: str = ""
    jira_project_key: str = ""

    # Confluence
    confluence_base_url: str = ""
    confluence_username: str = ""
    confluence_api_token: str = ""
    confluence_sprint_page_id: str = ""

    # Slack
    slack_bot_token: str = ""
    slack_channel_id: str = ""
    slack_report_time: str = "09:00"
    slack_report_enabled: bool = False

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

    def validate_confluence(self) -> list[str]:
        """Confluence 관련 필수 설정값 검증."""
        errors: list[str] = []
        if not self.confluence_base_url:
            errors.append("CONFLUENCE_BASE_URL")
        if not self.confluence_username:
            errors.append("CONFLUENCE_USERNAME")
        if not self.confluence_api_token:
            errors.append("CONFLUENCE_API_TOKEN")
        if not self.confluence_sprint_page_id:
            errors.append("CONFLUENCE_SPRINT_PAGE_ID")
        return errors

    def validate_slack(self) -> list[str]:
        """슬랙 리포트 관련 설정값 검증."""
        errors: list[str] = []
        if not self.slack_bot_token:
            errors.append("SLACK_BOT_TOKEN")
        if not self.slack_channel_id:
            errors.append("SLACK_CHANNEL_ID")
        return errors


def load_config() -> Config:
    """환경 변수에서 설정을 로드한다."""
    load_dotenv()

    return Config(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
        flask_port=int(os.getenv("FLASK_PORT", "5000")),
        flask_debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        flask_secret_key=os.getenv("FLASK_SECRET_KEY", "change-me"),
        jira_base_url=os.getenv("JIRA_BASE_URL", ""),
        jira_username=os.getenv("JIRA_USERNAME", ""),
        jira_password=os.getenv("JIRA_PASSWORD", ""),
        jira_board_id=os.getenv("JIRA_BOARD_ID", ""),
        jira_project_key=os.getenv("JIRA_PROJECT_KEY", ""),
        confluence_base_url=os.getenv("CONFLUENCE_BASE_URL", ""),
        confluence_username=os.getenv("CONFLUENCE_USERNAME", ""),
        confluence_api_token=os.getenv("CONFLUENCE_API_TOKEN", ""),
        confluence_sprint_page_id=os.getenv("CONFLUENCE_SPRINT_PAGE_ID", ""),
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
        slack_channel_id=os.getenv("SLACK_CHANNEL_ID", ""),
        slack_report_time=os.getenv("SLACK_REPORT_TIME", "09:00"),
        slack_report_enabled=os.getenv("SLACK_REPORT_ENABLED", "false").lower()
        == "true",
    )
