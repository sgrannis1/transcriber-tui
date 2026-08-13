"""File picker — a modal screen with a filtered directory tree for audio files."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Static

# Extensions faster-whisper (via ffmpeg) can decode.
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".opus",
    ".webm", ".mp4", ".m4b", ".amr", ".caf", ".aiff", ".aif", ".mov",
    ".wmv", ".mpga", ".mkv", ".mka", ".ape", ".wv", ".3gp", ".ts",
}


class AudioFileTree(DirectoryTree):
    """A directory tree that shows only directories and audio/video files."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() in AUDIO_EXTENSIONS
        ]


class FilePickerScreen(ModalScreen[Path | None]):
    """Modal screen for picking an audio file via a directory tree."""

    CSS = """
    FilePickerScreen {
        align: center middle;
    }
    #picker-dialog {
        width: 80%;
        height: 80%;
        border: round $primary;
        background: $surface;
    }
    #picker-title {
        height: 1;
        padding: 0 1;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    #picker-hint {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #picker-tree {
        height: 1fr;
        padding: 0 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, start_path: str | Path = "~") -> None:
        super().__init__()
        self._start_path = Path(start_path).expanduser()

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-dialog"):
            yield Static("Select an audio file", id="picker-title")
            yield Static(
                "Arrow keys to navigate, Enter to open/select, Esc to cancel",
                id="picker-hint",
            )
            yield AudioFileTree(self._start_path, id="picker-tree")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """A file was chosen — return its path."""
        self.dismiss(event.path)

    def action_cancel(self) -> None:
        self.dismiss(None)