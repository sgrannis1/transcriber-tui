"""Markdown export for transcripts and summaries."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def build_markdown(
    *,
    audio_path: str = "",
    transcript_text: str = "",
    summary_text: str = "",
    prompt_name: str = "",
    backend: str = "",
    model: str = "",
    whisper_model: str = "",
) -> str:
    """Render a transcript + summary as a single markdown document.

    Includes a metadata header (source file, backend/model used, prompt
    preset, generation timestamp) so the exported file is self-describing
    once it leaves the TUI.
    """
    title = Path(audio_path).stem if audio_path else "Transcript"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = [f"# {title}", ""]

    lines.append("## Metadata")
    lines.append("")
    if audio_path:
        lines.append(f"- **Source audio:** `{audio_path}`")
    lines.append(f"- **Generated:** {timestamp}")
    if prompt_name:
        lines.append(f"- **Prompt preset:** `{prompt_name}`")
    if backend:
        model_part = f" ({model})" if model else ""
        lines.append(f"- **Summarization backend:** `{backend}`{model_part}")
    if whisper_model:
        lines.append(f"- **Whisper model:** `{whisper_model}`")
    lines.append("")

    if summary_text:
        lines.append("## Summary")
        lines.append("")
        lines.append(summary_text.strip())
        lines.append("")

    if transcript_text:
        lines.append("## Transcript")
        lines.append("")
        lines.append(transcript_text.strip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def default_export_path(audio_path: str = "", export_dir: str | Path | None = None) -> Path:
    """Choose a sensible default .md path for the export.

    Prefers, in order: an explicit *export_dir* (e.g. from EXPORT_DIR in
    .env), the same directory as the source audio file, then finally the
    current working directory. Names the file after the audio file's
    stem plus a timestamp, so repeated exports never silently overwrite
    each other.
    """
    stem = Path(audio_path).stem if audio_path else "transcript"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{stem}-summary-{timestamp}.md"

    if export_dir:
        directory = Path(export_dir).expanduser()
    elif audio_path:
        directory = Path(audio_path).expanduser().resolve().parent
    else:
        directory = Path.cwd()

    return directory / filename


def save_markdown(
    content: str,
    path: str | Path,
) -> Path:
    """Write markdown content to *path*, creating parent directories as needed."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
