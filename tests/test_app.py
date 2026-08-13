"""Headless tests for the TUI app."""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Label, TextArea

from transcriber.app import TranscriberApp


@pytest.mark.asyncio
async def test_app_composes() -> None:
    """All key widgets are present after composition."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.query_one("#file-input", Input) is not None
        assert app.query_one("#browse-btn", Button) is not None
        assert app.query_one("#transcribe-btn", Button) is not None
        assert app.query_one("#export-btn", Button) is not None
        assert app.query_one("#transcript-area", TextArea) is not None
        assert app.query_one("#summary-area", TextArea) is not None


@pytest.mark.asyncio
async def test_bindings_registered() -> None:
    """All keyboard bindings are mapped."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)):
        names = {b.key for b in app.BINDINGS}
        expected = {"q", "t", "s", "e", "r", "c", "b", "o", "d", "x"}
        assert expected.issubset(names)


@pytest.mark.asyncio
async def test_transcribe_no_file() -> None:
    """Transcribe with no file shows a status message (doesn't crash)."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_transcribe()
        await pilot.pause(0.1)
        # Should not have triggered any exception; status area may show a message.


@pytest.mark.asyncio
async def test_summarize_no_transcript() -> None:
    """Summarize with no transcript shows a status message."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_summarize()
        await pilot.pause(0.1)
        # Should not crash.


@pytest.mark.asyncio
async def test_cycle_prompt(monkeypatch, tmp_path) -> None:
    """Cycling prompt updates the index.

    Isolated via monkeypatched LAST_PROMPT_PATH — action_cycle_prompt calls
    PromptStore.remember_selected(), which without isolation would write
    into the real ~/.config/transcriber/last_prompt.txt.
    """
    from transcriber import prompts as prompts_mod

    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )

    app = TranscriberApp()
    async with app.run_test(size=(100, 30)):
        app._prompt_names = ["a", "b", "c"]
        app._prompt_index = 0  # reset: on_mount may have selected a default
        app.action_cycle_prompt()
        assert app._prompt_index == 1
        app.action_cycle_prompt()
        assert app._prompt_index == 2
        app.action_cycle_prompt()
        assert app._prompt_index == 0  # wraps around


@pytest.mark.asyncio
async def test_cycle_backend_updates_model_and_base_url() -> None:
    """Regression: B must update summarize_model/base_url, not a stale attr.

    Previously _update_meta and _do_summarize read a nonexistent
    Config.openrouter_model, so switching backends silently kept calling
    OpenRouter with an empty model name. This locks in the real fix.
    """
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app._config.summarize_backend == "openrouter"
        app.action_cycle_backend()
        await pilot.pause(0.05)
        assert app._config.summarize_backend == "ollama"
        assert app._config.summarize_model == "hermes-qwen35b:latest"
        assert app._config.summarize_base_url == "http://localhost:11434/v1"


@pytest.mark.asyncio
async def test_on_env_reloaded_applies_new_config(monkeypatch, tmp_path) -> None:
    """After editing .env, _on_env_reloaded must apply the new values live.

    Simulates what happens when the user presses D, edits .env in their
    editor to switch backends, and returns to the TUI — without this,
    edits to .env made mid-session would be invisible until restart.
    """
    env_path = tmp_path / ".env"
    env_path.write_text(
        "SUMMARIZE_BACKEND=ollama\nOLLAMA_MODEL=test-model:latest\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "transcriber.config._find_env_file", lambda: env_path
    )

    app = TranscriberApp()
    async with app.run_test(size=(100, 30)):
        assert app._config.summarize_backend == "openrouter"  # pre-edit default
        app._on_env_reloaded()
        assert app._config.summarize_backend == "ollama"
        assert app._config.summarize_model == "test-model:latest"


def test_resolve_env_path_creates_from_example(tmp_path, monkeypatch) -> None:
    """resolve_env_path seeds a new .env from .env.example when none exists.

    Fully isolated in tmp_path: never touches the real project's .env.
    """
    from transcriber import config as config_mod

    fake_root = tmp_path / "project"
    (fake_root / "transcriber").mkdir(parents=True)
    (fake_root / ".env.example").write_text("OPENROUTER_API_KEY=\n", encoding="utf-8")

    monkeypatch.setattr(config_mod, "_find_env_file", lambda: None)
    # config.py resolves project_root as Path(__file__).resolve().parent.parent;
    # point __file__ at a fake config.py under fake_root/transcriber/ so that
    # math lands on fake_root without touching anything real.
    monkeypatch.setattr(config_mod, "__file__", str(fake_root / "transcriber" / "config.py"))

    created = config_mod.resolve_env_path()
    assert created == fake_root / ".env"
    assert created.exists()
    assert created.read_text(encoding="utf-8") == "OPENROUTER_API_KEY=\n"


@pytest.mark.asyncio
async def test_default_prompt_is_meeting_summary_on_fresh_install(
    tmp_path, monkeypatch
) -> None:
    """Regression: a fresh install must land on meeting_summary, not the
    "custom" placeholder, when the app first mounts.

    Isolated from the real ~/.config/transcriber via monkeypatched paths,
    so this never reads or writes the user's actual prompt config.
    """
    from transcriber import prompts as prompts_mod

    fake_prompts_path = tmp_path / "prompts.yaml"
    monkeypatch.setattr(prompts_mod, "USER_PROMPTS_PATH", fake_prompts_path)
    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )

    app = TranscriberApp()
    async with app.run_test(size=(100, 30)):
        assert "meeting_summary" in app._prompt_names
        assert app._prompt_names[app._prompt_index] == "meeting_summary"


@pytest.mark.asyncio
async def test_action_edit_prompt_reloads_from_disk_after_editor_closes(
    monkeypatch, tmp_path
) -> None:
    """Regression: pressing E, editing prompts.yaml, and closing the
    editor must actually re-read the file from disk before showing
    "Prompts reloaded" -- previously it called _on_prompts_reloaded()
    directly without ever calling store.reload(), so the in-memory
    prompts (and therefore what S actually sends the LLM) silently kept
    using the pre-edit text until the user separately pressed R.
    """
    from contextlib import contextmanager
    from unittest.mock import patch

    from transcriber import prompts as prompts_mod

    fake_prompts_path = tmp_path / "prompts.yaml"
    monkeypatch.setattr(prompts_mod, "USER_PROMPTS_PATH", fake_prompts_path)
    monkeypatch.setattr(
        prompts_mod, "LAST_PROMPT_PATH", tmp_path / "last_prompt.txt"
    )
    monkeypatch.delenv("EDITOR", raising=False)

    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.1)
        original = app._store.get("custom")
        assert original != "EDITED BY TEST"

        @contextmanager
        def fake_suspend():
            yield

        def fake_subprocess_call(cmd):
            # Simulate the external editor changing the file on disk.
            data = app._store.prompts.copy()
            data["custom"] = "EDITED BY TEST"
            fake_prompts_path.write_text(
                __import__("yaml").safe_dump(data), encoding="utf-8"
            )
            return 0

        with patch.object(app, "suspend", fake_suspend), patch(
            "transcriber.app.subprocess.call", side_effect=fake_subprocess_call
        ):
            app.action_edit_prompt()
            await pilot.pause(0.1)

        assert app._store.get("custom") == "EDITED BY TEST"


@pytest.mark.asyncio
async def test_export_markdown_with_nothing_shows_status_not_crash() -> None:
    """Pressing X with no transcript and no summary yet must not crash."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_export_markdown()
        await pilot.pause(0.1)
        # Should not raise; nothing to assert beyond "didn't crash".


@pytest.mark.asyncio
async def test_export_markdown_writes_real_file(tmp_path) -> None:
    """The core feature request: X must actually produce a readable .md
    file on disk containing the transcript and summary, viewable outside
    the TUI."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        audio_path = tmp_path / "meeting.mp3"
        audio_path.write_text("fake")
        app.query_one("#file-input", Input).value = str(audio_path)
        app._transcript_text = "[00:00] This is the transcript."
        app._summary_text = "## Summary\nThis is the summary."

        app.action_export_markdown()
        await pilot.pause(0.1)

        exported = list(tmp_path.glob("meeting-summary-*.md"))
        assert len(exported) == 1
        content = exported[0].read_text(encoding="utf-8")
        assert "This is the transcript." in content
        assert "This is the summary." in content
        assert "# meeting" in content

        status = str(app.query_one("#status", Label).render())
        assert "Exported to" in status


@pytest.mark.asyncio
async def test_export_markdown_respects_export_dir_config(tmp_path) -> None:
    """EXPORT_DIR in .env, once loaded into Config, must redirect exports
    there instead of next to the source audio."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        export_dir = tmp_path / "exports"
        app._config.export_dir = str(export_dir)

        audio_path = tmp_path / "audio" / "call.mp3"
        audio_path.parent.mkdir()
        audio_path.write_text("fake")
        app.query_one("#file-input", Input).value = str(audio_path)
        app._summary_text = "content"

        app.action_export_markdown()
        await pilot.pause(0.1)

        assert list(export_dir.glob("call-summary-*.md"))
        assert not list(audio_path.parent.glob("*.md"))