"""매일 아침 슬랙 리포트 스케줄러 모듈."""

from __future__ import annotations

from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from sprintlens.logging_config import get_logger
from sprintlens.slack_report_formatter import format_slack_report
from sprintlens.slack_service import SlackService

logger = get_logger(__name__)


class ReportScheduler:
    """매일 아침 정해진 시각에 슬랙으로 리포트를 발송하는 스케줄러."""

    def __init__(
        self,
        slack_service: SlackService,
        schedule_builder: Callable,
        *,
        report_time: str = "09:00",
        dashboard_url: str = "",
    ) -> None:
        self._slack_service = slack_service
        self._schedule_builder = schedule_builder
        self._dashboard_url = dashboard_url
        self._scheduler = BackgroundScheduler(timezone="Asia/Seoul")

        hour, minute = report_time.split(":")
        self._scheduler.add_job(
            self._send_daily_report,
            "cron",
            hour=int(hour),
            minute=int(minute),
            day_of_week="mon-fri",
            id="daily_slack_report",
        )

    def start(self) -> None:
        """스케줄러를 시작한다."""
        self._scheduler.start()
        logger.info("슬랙 리포트 스케줄러 시작")

    def shutdown(self) -> None:
        """스케줄러를 종료한다."""
        self._scheduler.shutdown()
        logger.info("슬랙 리포트 스케줄러 종료")

    def send_now(self) -> bool:
        """즉시 리포트를 발송한다 (수동 테스트용)."""
        return self._send_daily_report()

    def _send_daily_report(self) -> bool:
        """일일 리포트를 생성하여 슬랙에 발송한다."""
        try:
            schedule = self._schedule_builder()
            if not schedule:
                logger.warning("리포트 생성 실패: 스프린트 일정 없음")
                return False

            text = format_slack_report(
                schedule, dashboard_url=self._dashboard_url
            )
            return self._slack_service.send_message(text)
        except Exception:
            logger.exception("일일 리포트 발송 중 오류 발생")
            return False
