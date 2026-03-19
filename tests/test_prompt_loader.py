"""PromptLoader 모듈 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from sprintlens.prompt_loader import PromptLoader


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    """테스트용 프롬프트 디렉터리를 생성한다."""
    template = tmp_path / "test_template.txt"
    template.write_text("질문: {question}\n답변자: {answerer}", encoding="utf-8")
    return tmp_path


class TestPromptLoader:
    """PromptLoader 테스트."""

    def test_템플릿_로드_및_변수_치환(self, prompts_dir: Path) -> None:
        loader = PromptLoader(prompts_dir)
        result = loader.load(
            "test_template.txt", question="테스트", answerer="AI"
        )
        assert result == "질문: 테스트\n답변자: AI"

    def test_존재하지_않는_디렉터리(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="디렉토리"):
            PromptLoader(tmp_path / "nonexistent")

    def test_존재하지_않는_템플릿(self, prompts_dir: Path) -> None:
        loader = PromptLoader(prompts_dir)
        with pytest.raises(FileNotFoundError, match="템플릿"):
            loader.load("nonexistent.txt")

    def test_누락된_변수는_KeyError(self, prompts_dir: Path) -> None:
        loader = PromptLoader(prompts_dir)
        with pytest.raises(KeyError):
            loader.load("test_template.txt", question="테스트")
