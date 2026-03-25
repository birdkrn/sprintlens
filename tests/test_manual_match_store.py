"""manual_match_store 모듈 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from sprintlens.manual_match_store import ManualMatchStore


@pytest.fixture
def store(tmp_path: Path) -> ManualMatchStore:
    return ManualMatchStore(db_path=tmp_path / "manual_matches.db")


class TestManualMatchStore:
    """ManualMatchStore CRUD 테스트."""

    def test_오버라이드_저장_후_조회한다(self, store):
        store.set_override("page1", "GM-101", "글로벌", "GMG 빌드")

        overrides = store.get_overrides("page1")
        assert overrides == {"GM-101": ("글로벌", "GMG 빌드")}

    def test_같은_이슈_재설정_시_덮어쓴다(self, store):
        store.set_override("page1", "GM-101", "글로벌", "빌드 작업")
        store.set_override("page1", "GM-101", "개발", "엔진 업데이트")

        overrides = store.get_overrides("page1")
        assert overrides == {"GM-101": ("개발", "엔진 업데이트")}

    def test_오버라이드_삭제한다(self, store):
        store.set_override("page1", "GM-101", "글로벌", "빌드")
        store.remove_override("page1", "GM-101")

        assert store.get_overrides("page1") == {}

    def test_존재하지_않는_오버라이드_삭제는_에러없이_동작한다(self, store):
        store.remove_override("page1", "nonexistent")

    def test_페이지별로_독립적으로_관리된다(self, store):
        store.set_override("page1", "GM-101", "글로벌", "빌드")
        store.set_override("page2", "GM-101", "개발", "엔진")

        assert store.get_overrides("page1") == {"GM-101": ("글로벌", "빌드")}
        assert store.get_overrides("page2") == {"GM-101": ("개발", "엔진")}

    def test_전체_삭제한다(self, store):
        store.set_override("page1", "GM-101", "글로벌", "빌드")
        store.set_override("page1", "GM-102", "개발", "엔진")

        store.clear("page1")
        assert store.get_overrides("page1") == {}

    def test_빈_페이지는_빈_딕셔너리를_반환한다(self, store):
        assert store.get_overrides("nonexistent") == {}
