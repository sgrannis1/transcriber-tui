"""Tests for the file-per-prompt PromptStore."""

from __future__ import annotations

import yaml
import pytest

from transcriber.prompts import PromptsError, PromptStore, _BUILTIN_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_prompt(store: PromptStore, name: str, text: str) -> None:
    """Write a single prompt ``.md`` file (simulating an external edit)."""
    store.file_for(name).parent.mkdir(parents=True, exist_ok=True)
    store.file_for(name).write_text(text, encoding="utf-8")


# ===================================================================
# Creation & defaults
# ===================================================================


def test_ensure_exists_creates_directory_and_defaults(tmp_path) -> None:
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    assert store._dir.is_dir()
    for name in _BUILTIN_NAMES:
        assert store.file_for(name).exists(), f"{name}.md missing"


def test_load_seeds_defaults_when_directory_is_empty(tmp_path) -> None:
    store = PromptStore(tmp_path / "prompts")
    store._dir.mkdir(parents=True, exist_ok=True)  # empty dir, no files
    prompts = store.load()
    assert "custom" in prompts
    assert "meeting_summary" in prompts


def test_load_picks_up_new_dropped_in_file(tmp_path) -> None:
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    _write_prompt(store, "extra", "a hand-written prompt")
    store.reload()
    assert store.get("extra") == "a hand-written prompt"
    assert "extra" in store.names()


# ===================================================================
# Round-trip & reload
# ===================================================================


def test_reload_picks_up_external_edit(tmp_path) -> None:
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    store.load()  # seed cache

    # Simulate the user editing the file in $EDITOR.
    _write_prompt(store, "custom", "EDITED TEXT")
    store.reload()
    assert store.get("custom") == "EDITED TEXT"


def test_round_trip_unicode(tmp_path) -> None:
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    _write_prompt(store, "custom", "日本語のテスト")
    store.reload()
    assert store.get("custom") == "日本語のテスト"


# ===================================================================
# Names & active-name selection
# ===================================================================


def test_names_sorted(tmp_path) -> None:
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    _write_prompt(store, "b", "b")
    _write_prompt(store, "a", "a")
    _write_prompt(store, "c", "c")
    store.reload()
    # Built-in names are always seeded, plus our extras.
    names = store.names()
    assert "a" in names
    assert "b" in names
    assert "c" in names
    assert names == sorted(names)


def test_active_name_prefers_meeting_summary_over_alphabetical(
    tmp_path, monkeypatch
) -> None:
    from transcriber import prompts as prompts_mod

    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    store.load()
    assert store.active_name() == "meeting_summary"


def test_active_name_falls_back_to_alphabetical_without_meeting_summary(
    tmp_path, monkeypatch
) -> None:
    from transcriber import prompts as prompts_mod

    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    _write_prompt(store, "custom", "c")
    _write_prompt(store, "quick_recap", "q")
    # Delete meeting_summary so it can't be the default.
    store.file_for("meeting_summary").unlink(missing_ok=True)
    store.reload()
    assert store.active_name() == "custom"  # alphabetically first


def test_active_name_remembers_last_selection_across_instances(
    tmp_path, monkeypatch
) -> None:
    from transcriber import prompts as prompts_mod

    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )
    store1 = PromptStore(tmp_path / "prompts")
    store1.ensure_exists()
    store1.load()
    store1.remember_selected("quick_recap")

    # A brand-new instance (simulating restart) must respect it.
    store2 = PromptStore(tmp_path / "prompts")
    store2.load()
    assert store2.active_name() == "quick_recap"


# ===================================================================
# Migration from the old single-YAML-file format
# ===================================================================


def test_migrate_yaml_splits_into_files(tmp_path) -> None:
    """A legacy prompts.yaml is split into individual .md files on load."""
    old = tmp_path / "prompts.yaml"
    old.write_text(
        yaml.safe_dump(
            {"custom": "legacy custom", "extra": "an extra prompt"}
        ),
        encoding="utf-8",
    )

    store = PromptStore(tmp_path / "prompts")
    store.load()

    # Old file renamed out of the way.
    assert not old.exists()
    assert (tmp_path / "prompts.yaml.migrated").exists()

    # Content migrated.
    assert store.get("custom") == "legacy custom"
    assert store.get("extra") == "an extra prompt"

    # Built-in names seeded even if the YAML didn't have them.
    for name in _BUILTIN_NAMES:
        assert store.get(name), f"{name} should exist after migration"


def test_migrate_broken_yaml_falls_back_to_defaults(tmp_path) -> None:
    """A broken legacy YAML file doesn't crash — defaults are used instead."""
    old = tmp_path / "prompts.yaml"
    old.write_text(": this is not valid YAML :::", encoding="utf-8")

    store = PromptStore(tmp_path / "prompts")
    store.load()

    assert not old.exists()  # renamed away
    # The store still has usable defaults.
    assert store.get("meeting_summary")
    assert store.get("custom")


# ===================================================================
# Error handling
# ===================================================================


def test_unreadable_file_surfaces_error_but_does_not_crash(tmp_path) -> None:
    """If a prompt file exists but is unreadable (e.g. permissions),
    load() raises PromptsError so the caller can report it."""
    store = PromptStore(tmp_path / "prompts")
    store.ensure_exists()
    store.load()

    # Replace a file with a directory (unreadable as text).
    store.file_for("custom").unlink()
    store.file_for("custom").mkdir()

    with pytest.raises(PromptsError):
        store.load()