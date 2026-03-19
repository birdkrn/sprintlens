"""프롬프트 템플릿 파일을 로드하고 변수를 치환하는 모듈."""

from __future__ import annotations

from pathlib import Path

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)


class PromptLoader:
    """프롬프트 템플릿 파일을 로드하고 변수를 치환한다."""

    def __init__(self, prompts_dir: Path) -> None:
        if not prompts_dir.is_dir():
            raise FileNotFoundError(
                f"프롬프트 디렉토리가 존재하지 않습니다: {prompts_dir}"
            )
        self._prompts_dir = prompts_dir

    def load(self, template_name: str, **variables: str) -> str:
        """프롬프트 템플릿 파일을 로드하고 변수를 치환한다.

        Args:
            template_name: 템플릿 파일명 (예: "match_schedule.txt").
            **variables: 치환할 변수.

        Returns:
            변수가 치환된 프롬프트 문자열.

        Raises:
            FileNotFoundError: 템플릿 파일이 존재하지 않을 때.
            KeyError: 템플릿에 필요한 변수가 누락되었을 때.
        """
        template_path = self._prompts_dir / template_name
        if not template_path.is_file():
            raise FileNotFoundError(
                f"프롬프트 템플릿 파일이 존재하지 않습니다: {template_path}"
            )

        template = template_path.read_text(encoding="utf-8")
        logger.info("프롬프트 템플릿 로드: %s", template_name)

        prompt = template.format_map(variables)
        logger.debug("프롬프트 변수 치환 완료: %d자", len(prompt))
        return prompt
