"""Slack 알림 서비스 모듈."""

import requests

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


class SlackService:
    """Slack Bot API를 통한 메시지 발송 서비스."""

    SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

    def __init__(self, bot_token: str, channel_id: str) -> None:
        self._bot_token = bot_token
        self._channel_id = channel_id

    def send_report(self, text: str) -> bool:
        """슬랙 채널에 리포트 메시지를 발송한다."""
        headers = {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "channel": self._channel_id,
            "text": text,
        }

        try:
            response = requests.post(
                self.SLACK_POST_MESSAGE_URL,
                headers=headers,
                json=payload,
                timeout=10,
            )
            data = response.json()
            if not data.get("ok"):
                logger.error("슬랙 메시지 발송 실패: %s", data.get("error"))
                return False
            logger.info("슬랙 리포트 발송 완료")
            return True
        except requests.RequestException:
            logger.exception("슬랙 API 요청 중 오류 발생")
            return False
