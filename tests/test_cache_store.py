"""CacheStore 모듈 테스트."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sprintlens.cache_store import CacheStore


class TestCacheStore:
    """CacheStore 테스트."""

    def test_저장_및_조회(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "test.db", ttl_minutes=60)
        store.set("key1", {"name": "테스트"})

        data, updated_at = store.get("key1")

        assert data == {"name": "테스트"}
        assert updated_at is not None
        assert isinstance(updated_at, datetime)

    def test_캐시_미스(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "test.db", ttl_minutes=60)

        data, updated_at = store.get("nonexistent")

        assert data is None
        assert updated_at is None

    def test_TTL_만료(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "test.db", ttl_minutes=0)
        store.set("key1", {"data": "value"})

        data, updated_at = store.get("key1")

        assert data is None
        assert updated_at is None

    def test_덮어쓰기(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "test.db", ttl_minutes=60)
        store.set("key1", {"version": 1})
        store.set("key1", {"version": 2})

        data, _ = store.get("key1")

        assert data == {"version": 2}

    def test_삭제(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "test.db", ttl_minutes=60)
        store.set("key1", {"data": "value"})
        store.invalidate("key1")

        data, _ = store.get("key1")

        assert data is None

    def test_리스트_저장(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "test.db", ttl_minutes=60)
        store.set("key1", [{"a": 1}, {"b": 2}])

        data, _ = store.get("key1")

        assert data == [{"a": 1}, {"b": 2}]

    def test_set은_저장_시각을_반환한다(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "test.db", ttl_minutes=60)

        updated_at = store.set("key1", {"data": "value"})

        assert isinstance(updated_at, datetime)
        assert updated_at.tzinfo is not None

    def test_DB_디렉터리_자동_생성(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sub" / "dir" / "cache.db"
        store = CacheStore(db_path, ttl_minutes=60)
        store.set("key1", {"ok": True})

        data, _ = store.get("key1")

        assert data == {"ok": True}
