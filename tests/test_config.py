"""Tests for config.py, particularly resolve_editor()."""
from __future__ import annotations

import pytest

from transcriber import config as config_mod


def test_resolve_editor_uses_env_var_when_installed(monkeypatch) -> None:
    """If $EDITOR is set and actually on PATH, use it as-is."""
    monkeypatch.setenv("EDITOR", "nano")
    monkeypatch.setattr(
        config_mod.shutil, "which", lambda cmd: "/usr/bin/nano" if cmd == "nano" else None
    )
    assert config_mod.resolve_editor() == "nano"


def test_resolve_editor_preserves_flags_in_env_var(monkeypatch) -> None:
    """$EDITOR with args (e.g. 'code --wait') is checked by its first token
    but returned whole, so the flags reach subprocess.call."""
    monkeypatch.setenv("EDITOR", "code --wait")
    monkeypatch.setattr(
        config_mod.shutil, "which", lambda cmd: "/usr/bin/code" if cmd == "code" else None
    )
    assert config_mod.resolve_editor() == "code --wait"


def test_resolve_editor_falls_back_when_env_var_editor_missing(monkeypatch) -> None:
    """Regression: this is exactly the bug the user hit. $EDITOR unset (or
    pointing at something not installed, e.g. a stale 'vim' default) must
    fall through to an editor that actually exists, not crash later with
    a raw FileNotFoundError from subprocess."""
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(
        config_mod.shutil, "which",
        lambda cmd: "/usr/bin/nano" if cmd == "nano" else None,
    )
    assert config_mod.resolve_editor() == "nano"


def test_resolve_editor_ignores_env_var_pointing_at_missing_binary(monkeypatch) -> None:
    """$EDITOR=vim on a machine without vim must not be trusted blindly --
    fall through to a real fallback instead of erroring downstream."""
    monkeypatch.setenv("EDITOR", "vim")
    monkeypatch.setattr(
        config_mod.shutil, "which",
        lambda cmd: "/usr/bin/nano" if cmd == "nano" else None,
    )
    assert config_mod.resolve_editor() == "nano"


def test_resolve_editor_tries_fallbacks_in_order(monkeypatch) -> None:
    """vi should be picked if nano isn't available but vi is."""
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(
        config_mod.shutil, "which",
        lambda cmd: "/usr/bin/vi" if cmd == "vi" else None,
    )
    assert config_mod.resolve_editor() == "vi"


def test_resolve_editor_raises_clear_error_when_nothing_found(monkeypatch) -> None:
    """No editor anywhere -> a clear, actionable error, not a bare crash."""
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(config_mod.shutil, "which", lambda cmd: None)

    with pytest.raises(config_mod.EditorNotFoundError) as exc_info:
        config_mod.resolve_editor()
    message = str(exc_info.value)
    assert "nano" in message  # mentions what it tried
    assert "EDITOR" in message  # tells the user how to fix it
