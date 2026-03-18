"""테스트 공통 픽스처."""

import os

import pytest


@pytest.fixture
def mock_env_vars(monkeypatch):
    """테스트용 환경 변수를 설정한다."""
    env = {
        "LOG_LEVEL": "DEBUG",
        "FLASK_HOST": "127.0.0.1",
        "FLASK_PORT": "5000",
        "FLASK_DEBUG": "false",
        "FLASK_SECRET_KEY": "test-secret",
        "JIRA_BASE_URL": "https://jira.test.com",
        "JIRA_USERNAME": "test_user",
        "JIRA_API_TOKEN": "test_token",
        "JIRA_BOARD_ID": "100",
        "JIRA_PROJECT_KEY": "TEST",
        "CONFLUENCE_BASE_URL": "https://confluence.test.com",
        "CONFLUENCE_USERNAME": "test_user",
        "CONFLUENCE_API_TOKEN": "test_token",
        "CONFLUENCE_SPRINT_PAGE_ID": "12345",
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_CHANNEL_ID": "C12345",
        "SLACK_REPORT_TIME": "09:00",
        "SLACK_REPORT_ENABLED": "false",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture
def clean_env(monkeypatch):
    """모든 관련 환경 변수를 제거한다."""
    keys = [
        "LOG_LEVEL", "FLASK_HOST", "FLASK_PORT", "FLASK_DEBUG",
        "FLASK_SECRET_KEY", "JIRA_BASE_URL", "JIRA_USERNAME",
        "JIRA_API_TOKEN", "JIRA_BOARD_ID", "JIRA_PROJECT_KEY",
        "CONFLUENCE_BASE_URL", "CONFLUENCE_USERNAME",
        "CONFLUENCE_API_TOKEN", "CONFLUENCE_SPRINT_PAGE_ID",
        "SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID", "SLACK_REPORT_TIME",
        "SLACK_REPORT_ENABLED",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
