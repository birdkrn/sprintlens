"""Gemini 서비스 모듈 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors

from sprintlens.gemini_service import GeminiResponse, GeminiService


class TestGeminiResponse:
    """GeminiResponse 데이터 클래스 테스트."""

    def test_기본_응답_생성(self) -> None:
        response = GeminiResponse(text="응답 텍스트", model="gemini-2.0-flash")
        assert response.text == "응답 텍스트"
        assert response.model == "gemini-2.0-flash"
        assert response.thoughts == []

    def test_사고_과정_포함_응답(self) -> None:
        response = GeminiResponse(
            text="최종 답변",
            model="gemini-2.0-flash",
            thoughts=["사고 과정 1"],
        )
        assert response.thoughts == ["사고 과정 1"]

    def test_응답은_불변이다(self) -> None:
        response = GeminiResponse(text="테스트", model="gemini-2.0-flash")
        with pytest.raises(AttributeError):
            response.text = "변경"  # type: ignore[misc]


class TestGeminiService:
    """GeminiService 클래스 테스트."""

    @patch("sprintlens.gemini_service.genai.Client")
    def test_생성자가_Client를_생성한다(self, mock_cls: MagicMock) -> None:
        service = GeminiService(api_key="test-key")
        mock_cls.assert_called_once_with(api_key="test-key")
        assert service.model == "gemini-2.0-flash"

    @patch("sprintlens.gemini_service.genai.Client")
    def test_커스텀_모델_지정(self, mock_cls: MagicMock) -> None:
        service = GeminiService(api_key="test-key", model="gemini-2.5-pro")
        assert service.model == "gemini-2.5-pro"

    def test_빈_API_키는_ValueError(self) -> None:
        with pytest.raises(ValueError, match="API 키"):
            GeminiService(api_key="")

    def test_빈_모델명은_ValueError(self) -> None:
        with pytest.raises(ValueError, match="모델명"):
            GeminiService(api_key="test-key", model="")

    @patch("sprintlens.gemini_service.genai.Client")
    def test_프롬프트_전송_및_응답(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_response = _build_mock_response(
            parts=[{"thought": False, "text": "생성된 응답"}]
        )
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiService(api_key="test-key")
        result = service.generate_content("테스트 프롬프트")

        assert isinstance(result, GeminiResponse)
        assert result.text == "생성된 응답"
        assert result.model == "gemini-2.0-flash"
        mock_client.models.generate_content.assert_called_once()

    @patch("sprintlens.gemini_service.genai.Client")
    def test_사고_과정_분리(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_response = _build_mock_response(
            parts=[
                {"thought": True, "text": "사고 과정"},
                {"thought": False, "text": "최종 답변"},
            ]
        )
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiService(api_key="test-key")
        result = service.generate_content("프롬프트")

        assert result.text == "최종 답변"
        assert result.thoughts == ["사고 과정"]

    @patch("sprintlens.gemini_service.genai.Client")
    def test_옵션_전달(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_response = _build_mock_response(
            parts=[{"thought": False, "text": "응답"}]
        )
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiService(api_key="test-key")
        service.generate_content(
            "프롬프트",
            system_instruction="시스템 지침",
            temperature=0.5,
        )

        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["config"] is not None

    @patch("sprintlens.gemini_service.genai.Client")
    def test_빈_프롬프트는_ValueError(self, mock_cls: MagicMock) -> None:
        service = GeminiService(api_key="test-key")
        with pytest.raises(ValueError, match="프롬프트"):
            service.generate_content("")

    @patch("sprintlens.gemini_service.genai.Client")
    def test_None_텍스트는_빈_문자열(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_response = _build_mock_response(
            parts=[{"thought": False, "text": None}]
        )
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiService(api_key="test-key")
        result = service.generate_content("프롬프트")
        assert result.text == ""

    @patch("sprintlens.gemini_service.genai.Client")
    def test_candidates_없으면_fallback(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.text = "fallback 텍스트"
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiService(api_key="test-key")
        result = service.generate_content("프롬프트")
        assert result.text == "fallback 텍스트"

    @patch("sprintlens.gemini_service.genai.Client")
    def test_Config_파라미터_없으면_None(self, mock_cls: MagicMock) -> None:
        service = GeminiService(api_key="test-key")
        config = service._build_config()
        assert config is None

    @patch("sprintlens.gemini_service.genai.Client")
    def test_Config_파라미터_설정(self, mock_cls: MagicMock) -> None:
        service = GeminiService(api_key="test-key")
        config = service._build_config(
            system_instruction="지침",
            temperature=0.7,
            max_output_tokens=1000,
        )
        assert config is not None
        assert config.system_instruction == "지침"
        assert config.temperature == 0.7
        assert config.max_output_tokens == 1000

    @patch("sprintlens.gemini_service.time.sleep")
    @patch("sprintlens.gemini_service.genai.Client")
    def test_서버_오류_재시도_성공(
        self, mock_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = mock_cls.return_value
        mock_response = _build_mock_response(
            parts=[{"thought": False, "text": "재시도 성공"}]
        )
        mock_client.models.generate_content.side_effect = [
            genai_errors.ServerError("503", response_json={}),
            mock_response,
        ]

        service = GeminiService(api_key="test-key")
        result = service.generate_content("프롬프트")

        assert result.text == "재시도 성공"
        assert mock_client.models.generate_content.call_count == 2
        mock_sleep.assert_called_once_with(5)

    @patch("sprintlens.gemini_service.time.sleep")
    @patch("sprintlens.gemini_service.genai.Client")
    def test_지수_백오프_적용(
        self, mock_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = mock_cls.return_value
        mock_response = _build_mock_response(
            parts=[{"thought": False, "text": "응답"}]
        )
        mock_client.models.generate_content.side_effect = [
            genai_errors.ServerError("503", response_json={}),
            genai_errors.ServerError("503", response_json={}),
            mock_response,
        ]

        service = GeminiService(api_key="test-key")
        result = service.generate_content("프롬프트")

        assert result.text == "응답"
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(5)
        mock_sleep.assert_any_call(10)

    @patch("sprintlens.gemini_service.time.sleep")
    @patch("sprintlens.gemini_service.genai.Client")
    def test_최대_재시도_초과_시_에러(
        self, mock_cls: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_client = mock_cls.return_value
        mock_client.models.generate_content.side_effect = (
            genai_errors.ServerError("503", response_json={})
        )

        service = GeminiService(api_key="test-key")
        with pytest.raises(genai_errors.ServerError):
            service.generate_content("프롬프트")

        assert mock_client.models.generate_content.call_count == 3
        assert mock_sleep.call_count == 2


def _build_mock_response(parts: list[dict]) -> MagicMock:
    """테스트용 Gemini API 응답 mock을 생성한다."""
    mock_parts = []
    for part_data in parts:
        mock_part = MagicMock()
        mock_part.thought = part_data["thought"]
        mock_part.text = part_data["text"]
        mock_parts.append(mock_part)

    mock_candidate = MagicMock()
    mock_candidate.content.parts = mock_parts

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    text_parts = [p["text"] or "" for p in parts if not p["thought"]]
    mock_response.text = "".join(text_parts) if text_parts else None

    return mock_response
