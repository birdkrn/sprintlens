"""SprintLens 로깅 설정 모듈."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """애플리케이션 로깅을 설정한다."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # 외부 라이브러리 로그 레벨 조정
    for lib in ("urllib3", "requests", "atlassian", "werkzeug"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """이름이 지정된 로거 인스턴스를 반환한다."""
    return logging.getLogger(name)
