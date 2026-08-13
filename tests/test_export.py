"""Tests for markdown export."""
from __future__ import annotations

from pathlib import Path

from transcriber.export import build_markdown, default_export_path, save_markdown


def test_build_markdown_includes_summary_and_transcript() -> None:
    md = build_markdown(
        audio_path="/home/user/recording.mp3",
        transcript_text="[00:00] Hello world.",
        summary_text="## Summary\nGreeting exchange.",
        prompt_name="meeting_summary",
        backend="openrouter",
        model="deepseek/deepseek-v4-flash-0731",
        whisper_model="base",
    )
    assert "# recording" in md
    assert "## Summary" in md
    assert "Greeting exchange." in md
    assert "## Transcript" in md
    assert "[00:00] Hello world." in md
    assert "meeting_summary" in md
    assert "openrouter" in md
    assert "deepseek/deepseek-v4-flash-0731" in md
    assert "base" in md
    assert "/home/user/recording.mp3" in md


def test_build_markdown_without_transcript_omits_that_section() -> None:
    md = build_markdown(summary_text="Just a summary.")
    assert "## Summary" in md
    assert "## Transcript" not in md


def test_build_markdown_without_summary_omits_that_section() -> None:
    md = build_markdown(transcript_text="Just a transcript.")
    assert "## Transcript" in md
    assert "## Summary" not in md


def test_build_markdown_no_audio_path_uses_generic_title() -> None:
    md = build_markdown(summary_text="x")
    assert md.startswith("# Transcript")


def test_default_export_path_uses_audio_directory(tmp_path: Path) -> None:
    audio = tmp_path / "meeting.mp3"
    audio.write_text("fake audio")
    path = default_export_path(str(audio))
    assert path.parent == tmp_path
    assert path.name.startswith("meeting-summary-")
    assert path.suffix == ".md"


def test_default_export_path_prefers_explicit_export_dir(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    audio = audio_dir / "meeting.mp3"
    audio.write_text("fake audio")

    export_dir = tmp_path / "exports"
    path = default_export_path(str(audio), export_dir=str(export_dir))
    assert path.parent == export_dir
    assert path.name.startswith("meeting-summary-")


def test_default_export_path_falls_back_to_cwd_without_audio_path() -> None:
    path = default_export_path()
    assert path.name.startswith("transcript-summary-")


def test_save_markdown_writes_file_and_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "out.md"
    result = save_markdown("# Hello\n", target)
    assert result == target
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "# Hello\n"


def test_save_markdown_expands_user(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = save_markdown("content", "~/exported.md")
    assert result == tmp_path / "exported.md"
    assert result.read_text(encoding="utf-8") == "content"


def test_two_exports_of_same_audio_do_not_collide(tmp_path: Path) -> None:
    """Regression safeguard: repeated exports must not silently overwrite
    each other -- the timestamp in the filename should differ across
    calls separated by at least a second, and even within the same
    second the caller is expected to have distinct content, not a name
    collision that clobbers prior work."""
    import time

    audio = tmp_path / "call.mp3"
    audio.write_text("x")
    p1 = default_export_path(str(audio))
    time.sleep(1.05)
    p2 = default_export_path(str(audio))
    assert p1 != p2
