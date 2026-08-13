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


def test_active_name_prefers_meeting_summary_over_alphabetical(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: a fresh install must default to meeting_summary, not
    "custom" (which sorts first alphabetically and is a placeholder, not
    a usable prompt)."""
    from transcriber import prompts as prompts_mod

    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )
    store = PromptStore(tmp_path / "prompts.yaml")
    store.save({"custom": "1", "meeting_summary": "2", "quick_recap": "3"})
    store.reload()
    assert store.active_name() == "meeting_summary"


def test_active_name_falls_back_to_alphabetical_without_meeting_summary(
    tmp_path: Path, monkeypatch
) -> None:
    """If meeting_summary isn't present at all, fall back gracefully."""
    from transcriber import prompts as prompts_mod

    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )
    store = PromptStore(tmp_path / "prompts.yaml")
    store.save({"custom": "1", "quick_recap": "3"})
    store.reload()
    assert store.active_name() == "custom"  # alphabetically first of the two


def test_active_name_remembers_last_selection_across_instances(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: once the user explicitly picks a prompt (C in the TUI),
    that choice must survive a restart (new PromptStore instance) rather
    than reverting to the meeting_summary default every time."""
    from transcriber import prompts as prompts_mod

    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )
    store1 = PromptStore(tmp_path / "prompts.yaml")
    store1.save({"custom": "1", "meeting_summary": "2", "quick_recap": "3"})
    store1.reload()
    store1.remember_selected("quick_recap")

    # A brand-new PromptStore instance (simulating app restart) must see it.
    store2 = PromptStore(tmp_path / "prompts.yaml")
    store2.load()
    assert store2.active_name() == "quick_recap"


def test_active_name_returns_first(tmp_path: Path) -> None:
    store = PromptStore(tmp_path / "prompts.yaml")
    store.save({"b": "2", "a": "1"})
    store.reload()
    assert store.active_name() == "a"