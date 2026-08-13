"""Tests for the transcription module."""
from __future__ import annotations

import os

from transcriber.transcribe import Transcript, Segment, format_segments, transcribe


def test_format_segments() -> None:
    transcript = Transcript(
        text="Hello world",
        segments=[
            Segment(start=5.0, end=10.0, text="Hello"),
            Segment(start=12.0, end=15.0, text="world"),
        ],
    )
    formatted = format_segments(transcript)
    lines = formatted.split("\n")
    assert lines[0] == "[00:05] Hello"
    assert lines[1] == "[00:12] world"


def test_transcribe_real_file() -> None:
    """Integration test: transcribe a real audio file (skips if missing)."""
    path = "/home/sgrannis/voice-memos/taylor-swift-wedding-july-2026.mp3"
    if not os.path.exists(path):
        import pytest

        pytest.skip("test audio file not present")

    result = transcribe(path, model_size="base")
    assert result.language == "en"
    assert len(result.segments) > 5
    assert len(result.text) > 100