"""config 모듈 테스트."""

from sprintlens.config import Config, load_config


class TestConfig:
    """Config 데이터클래스 테스트."""

    def test_validate_all_required(self):
        """필수 항목이 모두 누락된 경우 에러 목록을 반환한다."""
        config = Config()
        errors = config.validate()
        assert "JIRA_BASE_URL" in errors
        assert "JIRA_USERNAME" in errors
        assert "JIRA_PASSWORD" in errors
        assert "JIRA_BOARD_ID" in errors
        assert "JIRA_PROJECT_KEY" in errors
        assert "CONFLUENCE_BASE_URL" in errors

    def test_validate_no_errors(self):
        """모든 필수 항목이 설정된 경우 빈 목록을 반환한다."""
        config = Config(
            jira_base_url="https://jira.test.com",
            jira_username="user",
            jira_password="password",
            jira_board_id="100",
            jira_project_key="TEST",
            confluence_base_url="https://confluence.test.com",
            confluence_username="user",
            confluence_api_token="token",
            confluence_sprint_page_id="12345",
        )
        assert config.validate() == []

    def test_validate_slack(self):
        """슬랙 설정 검증 테스트."""
        config = Config()
        errors = config.validate_slack()
        assert "SLACK_BOT_TOKEN" in errors
        assert "SLACK_CHANNEL_ID" in errors

    def test_validate_slack_no_errors(self):
        """슬랙 설정이 모두 있는 경우."""
        config = Config(slack_bot_token="xoxb-test", slack_channel_id="C123")
        assert config.validate_slack() == []


class TestLoadConfig:
    """load_config 함수 테스트."""

    def test_load_from_env(self, mock_env_vars):
        """환경 변수에서 설정을 올바르게 로드한다."""
        config = load_config()
        assert config.jira_base_url == "https://jira.test.com"
        assert config.jira_username == "test_user"
        assert config.flask_port == 5000
        assert config.slack_report_enabled is False

    def test_load_defaults(self, clean_env):
        """환경 변수 미설정시 기본값을 사용한다."""
        config = load_config()
        assert config.log_level == "INFO"
        assert config.flask_port == 5000
        assert config.flask_debug is False
        assert config.slack_report_time == "09:00"
