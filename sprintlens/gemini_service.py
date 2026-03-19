"""Google Gemini API를 통해 텍스트를 생성하는 서비스 모듈."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from sprintlens.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_MODEL = "gemini-2.0-flash"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 5


@dataclass(frozen=True)
class GeminiResponse:
    """Gemini API 응답을 담는 불변 데이터 클래스."""

    text: str
    model: str
    thoughts: list[str] = field(default_factory=list)


class GeminiService:
    """Google Gemini API를 통해 텍스트를 생성하는 서비스."""

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError("Gemini API 키가 비어있습니다.")
        if not model:
            raise ValueError("모델명이 비어있습니다.")
        self._model = model
        self._client = genai.Client(api_key=api_key)
        logger.info("GeminiService 초기화 완료 (모델: %s)", model)

    @property
    def model(self) -> str:
        """사용 중인 모델명을 반환한다."""
        return self._model

    def generate_content(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> GeminiResponse:
        """프롬프트를 전송하고 Gemini 응답을 반환한다.

        Args:
            prompt: 사용자 프롬프트 텍스트.
            system_instruction: 시스템 지침 (선택).
            temperature: 생성 온도 0.0~2.0 (선택).
            max_output_tokens: 최대 출력 토큰 수 (선택).

        Returns:
            Gemini 응답 데이터.

        Raises:
            ValueError: 프롬프트가 비어있는 경우.
            google.genai.errors.ClientError: API 클라이언트 오류 (4xx).
            google.genai.errors.ServerError: API 서버 오류 (5xx, 재시도 초과).
        """
        if not prompt.strip():
            raise ValueError("프롬프트가 비어있습니다.")

        config = self._build_config(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        logger.info(
            "Gemini API 호출: model=%s, prompt_length=%d",
            self._model,
            len(prompt),
        )

        response = self._call_api_with_retry(prompt, config)

        text, thoughts = self._parse_response(response)
        logger.info("Gemini 응답 수신: response_length=%d", len(text))

        return GeminiResponse(text=text, model=self._model, thoughts=thoughts)

    def _call_api_with_retry(
        self,
        prompt: str,
        config: types.GenerateContentConfig | None,
    ) -> types.GenerateContentResponse:
        """서버 오류(5xx) 발생 시 지수 백오프로 재시도한다."""
        for attempt in range(_MAX_RETRIES):
            try:
                return self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
            except genai_errors.ServerError:
                if attempt == _MAX_RETRIES - 1:
                    raise
                delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "Gemini 서버 오류, %d초 후 재시도 (%d/%d)",
                    delay,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                time.sleep(delay)
        raise RuntimeError("재시도 횟수 초과")  # pragma: no cover

    @staticmethod
    def _parse_response(
        response: types.GenerateContentResponse,
    ) -> tuple[str, list[str]]:
        """API 응답에서 텍스트와 사고 과정을 분리한다."""
        thoughts: list[str] = []
        text_parts: list[str] = []

        if not response.candidates:
            return response.text or "", thoughts

        for part in response.candidates[0].content.parts:
            if part.thought:
                thoughts.append(part.text or "")
            else:
                text_parts.append(part.text or "")

        text = "".join(text_parts) if text_parts else response.text or ""
        return text, thoughts

    def _build_config(
        self,
        *,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> types.GenerateContentConfig | None:
        """GenerateContentConfig를 생성한다.

        모든 파라미터가 None이면 None을 반환하여 SDK 기본값을 사용한다.
        """
        kwargs: dict = {}
        if system_instruction is not None:
            kwargs["system_instruction"] = system_instruction
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens

        if not kwargs:
            return None

        return types.GenerateContentConfig(**kwargs)
