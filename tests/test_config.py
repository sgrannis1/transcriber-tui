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


def _base_env(monkeypatch, **overrides) -> None:
    """Minimal env for load_config(): openrouter backend, no .env file."""
    monkeypatch.setattr(config_mod, "_find_env_file", lambda: None)
    monkeypatch.delenv("SUMMARIZE_BACKEND", raising=False)
    monkeypatch.delenv("SUMMARIZE_MODEL", raising=False)
    monkeypatch.delenv("SUMMARIZE_BASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def test_load_config_rejects_openai_key_in_openrouter_slot(monkeypatch) -> None:
    """Regression: this is the exact bug the user hit. Pasting an OpenAI
    key (sk-proj-...) into OPENROUTER_API_KEY must fail immediately with
    a specific, actionable ConfigError -- not silently pass config
    loading and only fail later with OpenRouter's confusing generic
    "Missing Authentication header" 401 after a real network round-trip.
    """
    _base_env(
        monkeypatch,
        OPENROUTER_API_KEY="sk-proj-abc123def456",
    )
    with pytest.raises(config_mod.ConfigError) as exc_info:
        config_mod.load_config()
    message = str(exc_info.value)
    assert "OpenAI" in message
    assert "sk-proj-" in message
    assert "openrouter.ai/keys" in message


def test_load_config_rejects_anthropic_key_in_openrouter_slot(monkeypatch) -> None:
    """Same class of mistake with an Anthropic-shaped key."""
    _base_env(
        monkeypatch,
        OPENROUTER_API_KEY="sk-ant-abc123def456",
    )
    with pytest.raises(config_mod.ConfigError) as exc_info:
        config_mod.load_config()
    assert "Anthropic" in str(exc_info.value)


def test_load_config_accepts_real_openrouter_key(monkeypatch) -> None:
    """A correctly-shaped OpenRouter key must load without error."""
    _base_env(
        monkeypatch,
        OPENROUTER_API_KEY="sk-or-v1-" + "a" * 64,
    )
    cfg = config_mod.load_config()
    assert cfg.openrouter_api_key.startswith("sk-or-")


def test_load_config_does_not_validate_key_for_local_backends(monkeypatch) -> None:
    """An OpenAI-shaped key sitting unused in OPENROUTER_API_KEY must not
    block loading when the active backend doesn't even use OpenRouter."""
    _base_env(
        monkeypatch,
        SUMMARIZE_BACKEND="ollama",
        OLLAMA_MODEL="test-model",
        OPENROUTER_API_KEY="sk-proj-leftover-from-another-app",
    )
    cfg = config_mod.load_config()  # must not raise
    assert cfg.summarize_backend == "ollama"
