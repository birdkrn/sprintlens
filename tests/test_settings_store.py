"""SettingsStore 모듈 테스트."""

from __future__ import annotations

from pathlib import Path

from sprintlens.settings_store import SettingsStore


class TestSettingsStore:
    """SettingsStore 테스트."""

    def test_저장_및_조회(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path / "test.db")
        store.set("key1", "value1")
        assert store.get("key1") == "value1"

    def test_기본값_반환(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path / "test.db")
        assert store.get("nonexistent", "default") == "default"

    def test_빈_기본값(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path / "test.db")
        assert store.get("nonexistent") == ""

    def test_덮어쓰기(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path / "test.db")
        store.set("key1", "v1")
        store.set("key1", "v2")
        assert store.get("key1") == "v2"

    def test_get_all(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path / "test.db")
        store.set("a", "1")
        store.set("b", "2")
        result = store.get_all()
        assert result == {"a": "1", "b": "2"}

    def test_set_many(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path / "test.db")
        store.set_many({"x": "10", "y": "20"})
        assert store.get("x") == "10"
        assert store.get("y") == "20"

    def test_DB_디렉터리_자동_생성(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sub" / "settings.db"
        store = SettingsStore(db_path)
        store.set("key1", "ok")
        assert store.get("key1") == "ok"
