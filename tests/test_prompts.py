"""Tests for the PromptStore."""
from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from transcriber.prompts import PromptStore


def test_ensure_exists_creates_defaults(tmp_path: Path) -> None:
    store = PromptStore(tmp_path / "prompts.yaml")
    store.ensure_exists()
    assert store.path.exists()
    assert "meeting_summary" in store.prompts or "custom" in store.prompts


def test_load_empty_file_returns_defaults(tmp_path: Path) -> None:
    p = tmp_path / "prompts.yaml"
    p.write_text("", encoding="utf-8")
    store = PromptStore(p)
    prompts = store.load()
    assert "custom" in prompts


def test_reload_picks_up_edit(tmp_path: Path) -> None:
    p = tmp_path / "prompts.yaml"
    store = PromptStore(p)
    store.save({"custom": "original"})
    store.load()

    # Simulate external edit.
    with open(p, "w", encoding="utf-8") as fh:
        yaml.safe_dump({"custom": "EDITED"}, fh)
    store.reload()
    assert store.get("custom") == "EDITED"


def test_round_trip_unicode(tmp_path: Path) -> None:
    store = PromptStore(tmp_path / "prompts.yaml")
    store.save({"custom": "日本語のテスト"})
    store.reload()
    assert store.get("custom") == "日本語のテスト"


def test_names_sorted(tmp_path: Path) -> None:
    store = PromptStore(tmp_path / "prompts.yaml")
    store.save({"b": "2", "a": "1", "c": "3"})
    store.reload()
    assert store.names() == ["a", "b", "c"]


def test_active_name_returns_first(tmp_path: Path) -> None:
    store = PromptStore(tmp_path / "prompts.yaml")
    store.save({"b": "2", "a": "1"})
    store.reload()
    assert store.active_name() == "a"