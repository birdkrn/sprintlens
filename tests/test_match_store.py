"""match_store 모듈 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from sprintlens.match_store import MatchStore


@pytest.fixture
def store(tmp_path: Path) -> MatchStore:
    """임시 DB 경로를 사용하는 MatchStore."""
    return MatchStore(db_path=tmp_path / "matches.db")


@pytest.fixture
def sample_match_data() -> list[dict]:
    return [
        {
            "schedule_task": "GMG 빌드 및 전달",
            "assignee": "주세영",
            "matched_issues": [
                {"key": "GM-101", "summary": "빌드 전달", "status": "완료"}
            ],
            "match_confidence": "high",
        }
    ]


class TestMatchStore:
    """MatchStore CRUD 테스트."""

    def test_저장_후_조회한다(self, store, sample_match_data):
        store.save("page1", "hash_s", "hash_i", sample_match_data)

        result = store.get("page1")

        assert result is not None
        assert result.page_id == "page1"
        assert result.schedule_hash == "hash_s"
        assert result.issues_hash == "hash_i"
        assert result.match_data == sample_match_data
        assert result.updated_at is not None

    def test_존재하지_않는_페이지는_None을_반환한다(self, store):
        result = store.get("nonexistent")
        assert result is None

    def test_같은_페이지에_저장하면_덮어쓴다(self, store, sample_match_data):
        store.save("page1", "hash_old", "hash_old", sample_match_data)
        store.save("page1", "hash_new", "hash_new", [])

        result = store.get("page1")
        assert result.schedule_hash == "hash_new"
        assert result.match_data == []

    def test_삭제하면_조회할_수_없다(self, store, sample_match_data):
        store.save("page1", "hash_s", "hash_i", sample_match_data)

        store.delete("page1")

        assert store.get("page1") is None

    def test_존재하지_않는_페이지_삭제는_에러_없이_동작한다(self, store):
        store.delete("nonexistent")  # 예외 없이 통과

    def test_여러_페이지를_독립적으로_저장한다(self, store, sample_match_data):
        store.save("page1", "h1", "h1", sample_match_data)
        store.save("page2", "h2", "h2", [])

        assert store.get("page1").match_data == sample_match_data
        assert store.get("page2").match_data == []
