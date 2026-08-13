"""Local transcription via faster-whisper."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Segment:
    """A single transcribed segment with timestamps."""

    start: float
    end: float
    text: str


@dataclass
class Transcript:
    """A complete transcription result."""

    text: str
    segments: list[Segment] = field(default_factory=list)
    language: str = ""
    language_probability: float = 0.0
    duration: float = 0.0


# Module-level model cache, guarded by a lock for thread safety.
_MODEL_CACHE: dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()


def _get_model(model_size: str) -> Any:
    """Load (and cache) the Whisper model for a given size."""
    from faster_whisper import WhisperModel

    with _MODEL_LOCK:
        if model_size not in _MODEL_CACHE:
            _MODEL_CACHE[model_size] = WhisperModel(
                model_size, device="cpu", compute_type="int8"
            )
        return _MODEL_CACHE[model_size]


def transcribe(
    audio_path: str,
    model_size: str = "base",
    beam_size: int = 5,
) -> Transcript:
    """Transcribe an audio file.

    Runs in a worker thread in the TUI; this function is synchronous and
    can be called directly or wrapped in a thread.
    """
    model = _get_model(model_size)
    segments_iter, info = model.transcribe(audio_path, beam_size=beam_size)

    segments = [
        Segment(start=seg.start, end=seg.end, text=seg.text.strip())
        for seg in segments_iter
    ]
    full_text = " ".join(seg.text for seg in segments).strip()

    return Transcript(
        text=full_text,
        segments=segments,
        language=info.language,
        language_probability=info.language_probability,
        duration=info.duration,
    )


def format_segments(transcript: Transcript) -> str:
    """Render segments with timestamps for display in the TUI."""
    lines = []
    for seg in transcript.segments:
        stamp = f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}]"
        lines.append(f"{stamp} {seg.text}")
    return "\n".join(lines)
