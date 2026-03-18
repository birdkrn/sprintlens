"""매일 아침 슬랙 리포트 스케줄러 모듈."""

from apscheduler.schedulers.background import BackgroundScheduler

from sprintlens.logging_config import get_logger
from sprintlens.report_service import ReportService
from sprintlens.slack_service import SlackService

logger = get_logger(__name__)


class ReportScheduler:
    """매일 아침 정해진 시각에 슬랙으로 리포트를 발송하는 스케줄러."""

    def __init__(
        self,
        report_service: ReportService,
        slack_service: SlackService,
        report_time: str = "09:00",
    ) -> None:
        self._report_service = report_service
        self._slack_service = slack_service
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

    def _send_daily_report(self) -> None:
        """일일 리포트를 생성하여 슬랙에 발송한다."""
        try:
            report = self._report_service.generate_sprint_report()
            if not report:
                logger.warning("리포트 생성 실패: 활성 스프린트 없음")
                return

            text = self._report_service.format_slack_report(report)
            self._slack_service.send_report(text)
        except Exception:
            logger.exception("일일 리포트 발송 중 오류 발생")
