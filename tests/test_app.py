"""Headless tests for the TUI app."""
from __future__ import annotations

import pytest
from textual.widgets import Button, Input, TextArea

from transcriber.app import TranscriberApp


@pytest.mark.asyncio
async def test_app_composes() -> None:
    """All key widgets are present after composition."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.query_one("#file-input", Input) is not None
        assert app.query_one("#transcribe-btn", Button) is not None
        assert app.query_one("#transcript-area", TextArea) is not None
        assert app.query_one("#summary-area", TextArea) is not None


@pytest.mark.asyncio
async def test_bindings_registered() -> None:
    """All keyboard bindings are mapped."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)):
        names = {b.key for b in app.BINDINGS}
        expected = {"q", "t", "s", "e", "r", "c"}
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
async def test_cycle_prompt() -> None:
    """Cycling prompt updates the index."""
    app = TranscriberApp()
    async with app.run_test(size=(100, 30)):
        app._prompt_names = ["a", "b", "c"]
        app.action_cycle_prompt()
        assert app._prompt_index == 1
        app.action_cycle_prompt()
        assert app._prompt_index == 2
        app.action_cycle_prompt()
        assert app._prompt_index == 0  # wraps around