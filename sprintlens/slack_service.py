"""Slack Incoming Webhook 기반 메시지 발송 서비스 모듈."""

import requests

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


class SlackService:
    """Slack Incoming Webhook을 통한 메시지 발송 서비스."""

    def __init__(self, webhook_url: str) -> None:
        if not webhook_url:
            raise ValueError("Slack Webhook URL이 비어있습니다.")
        self._webhook_url = webhook_url

    def send_message(self, text: str) -> bool:
        """슬랙 채널에 메시지를 발송한다 (mrkdwn 형식)."""
        payload = {"text": text}

        try:
            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=10,
            )
            if response.status_code != 200 or response.text != "ok":
                logger.error(
                    "슬랙 메시지 발송 실패: %s %s",
                    response.status_code,
                    response.text,
                )
                return False
            logger.info("슬랙 메시지 발송 완료")
            return True
        except requests.RequestException:
            logger.exception("슬랙 Webhook 요청 중 오류 발생")
            return False
