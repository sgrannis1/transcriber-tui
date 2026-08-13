"""Tests for the file picker."""
from __future__ import annotations

from pathlib import Path

import pytest

from transcriber.picker import AUDIO_EXTENSIONS, AudioFileTree, FilePickerScreen


def test_audio_extensions_common() -> None:
    assert ".mp3" in AUDIO_EXTENSIONS
    assert ".wav" in AUDIO_EXTENSIONS
    assert ".ogg" in AUDIO_EXTENSIONS
    assert ".flac" in AUDIO_EXTENSIONS


def test_filter_paths_keeps_dirs_and_audio(tmp_path: Path) -> None:
    # Create a dir, an audio file, and a non-audio file.
    (tmp_path / "subdir").mkdir()
    audio = tmp_path / "recording.mp3"
    audio.write_text("x")
    non_audio = tmp_path / "notes.txt"
    non_audio.write_text("x")

    tree = AudioFileTree.__new__(AudioFileTree)  # avoid widget init
    kept = list(tree.filter_paths([tmp_path / "subdir", audio, non_audio]))

    names = {p.name for p in kept}
    assert "subdir" in names
    assert "recording.mp3" in names
    assert "notes.txt" not in names


def test_filter_paths_case_insensitive(tmp_path: Path) -> None:
    upper = tmp_path / "SONG.MP3"
    upper.write_text("x")
    tree = AudioFileTree.__new__(AudioFileTree)
    kept = list(tree.filter_paths([upper]))
    assert kept == [upper]


@pytest.mark.asyncio
async def test_picker_screen_composes() -> None:
    from textual.app import App

    class HostApp(App):
        def compose(self):
            return ()

    app = HostApp()
    async with app.run_test(size=(100, 30)) as pilot:
        screen = FilePickerScreen(Path.home())
        await pilot.app.push_screen(screen)
        await pilot.pause(0.1)
        assert screen.query_one("#picker-tree") is not None
        assert screen.query_one("#picker-title") is not None