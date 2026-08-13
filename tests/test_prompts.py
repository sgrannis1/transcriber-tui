"""Tests for the PromptStore."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from transcriber.prompts import PromptsError, PromptStore


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


def test_load_malformed_yaml_raises_promptserror_not_crash(tmp_path: Path) -> None:
    """Regression: the user's real prompt text contained unescaped double
    quotes inside a YAML double-quoted scalar (e.g. mentioning "said" vs
    "sad" and "Regen Street" in prose), which broke the YAML parser. This
    must surface as a specific, catchable PromptsError -- never a bare
    yaml.YAMLError bubbling up and crashing the whole TUI on startup.
    """
    p = tmp_path / "prompts.yaml"
    # Deliberately malformed: an unescaped " inside a double-quoted scalar.
    p.write_text(
        'meeting_summary: "Note: transcription errors like "said" vs "sad" happen."\n',
        encoding="utf-8",
    )
    store = PromptStore(p)
    with pytest.raises(PromptsError) as exc_info:
        store.load()
    message = str(exc_info.value)
    assert str(p) in message
    assert "quote" in message.lower()


def test_load_malformed_yaml_keeps_previously_loaded_prompts(tmp_path: Path) -> None:
    """If a good load already happened, a later reload() hitting broken
    YAML must not wipe out the good in-memory prompts -- e.g. R reloading
    a file the user just broke mid-edit shouldn't nuke what was working."""
    p = tmp_path / "prompts.yaml"
    store = PromptStore(p)
    store.save({"custom": "a good prompt"})
    store.load()
    assert store.get("custom") == "a good prompt"

    p.write_text('custom: "broken "quote" here"\n', encoding="utf-8")
    with pytest.raises(PromptsError):
        store.reload()
    # The previously-good prompt must still be there.
    assert store.get("custom") == "a good prompt"


def test_load_malformed_yaml_on_first_load_falls_back_to_defaults(
    tmp_path: Path,
) -> None:
    """If the very first load() ever hits broken YAML (nothing good was
    loaded before), fall back to the built-in defaults rather than an
    empty prompt store."""
    p = tmp_path / "prompts.yaml"
    p.write_text('custom: "broken "quote" here"\n', encoding="utf-8")
    store = PromptStore(p)
    with pytest.raises(PromptsError):
        store.load()
    assert store.names()  # not empty -- fell back to defaults
    assert "custom" in store.names()