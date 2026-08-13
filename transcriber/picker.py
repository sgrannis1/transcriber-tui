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
    """Modal screen for picking an audio file via a directory tree.

    Free navigation up and down the filesystem: the DirectoryTree's
    reactive .path is re-rooted on "go up" (Backspace/U/-), and expanding
    a folder (Enter/click) descends normally via the tree's own behavior.
    Not limited to the starting directory or the home directory.
    """

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
    #picker-path {
        height: 1;
        padding: 0 1;
        color: $accent;
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

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("backspace", "go_up", "Up a directory"),
        ("u", "go_up", "Up a directory"),
        ("minus", "go_up", "Up a directory"),
        ("h", "go_home", "Home"),
        ("g", "go_root", "Filesystem root (/)"),
    ]

    def __init__(self, start_path: str | Path = "~") -> None:
        super().__init__()
        self._start_path = Path(start_path).expanduser().resolve()

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-dialog"):
            yield Static("Select an audio file", id="picker-title")
            yield Static(str(self._start_path), id="picker-path")
            yield Static(
                "Enter: open/select   Backspace/U/-: up a directory   "
                "H: home   G: filesystem root   Esc: cancel",
                id="picker-hint",
            )
            yield AudioFileTree(self._start_path, id="picker-tree")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """A file was chosen — return its path."""
        self.dismiss(event.path)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Keep the visible current-path label in sync as the user browses."""
        self._update_path_label()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_go_up(self) -> None:
        """Re-root the tree one level up (unless already at the filesystem root)."""
        tree = self.query_one("#picker-tree", AudioFileTree)
        parent = tree.path.parent if isinstance(tree.path, Path) else Path(tree.path).parent
        if parent == tree.path:
            return  # already at filesystem root
        tree.path = parent
        self._update_path_label()

    def action_go_home(self) -> None:
        """Jump straight back to the user's home directory."""
        tree = self.query_one("#picker-tree", AudioFileTree)
        tree.path = Path.home()
        self._update_path_label()

    def action_go_root(self) -> None:
        """Jump straight to the filesystem root."""
        tree = self.query_one("#picker-tree", AudioFileTree)
        tree.path = Path(tree.path).anchor or "/"
        self._update_path_label()

    def _update_path_label(self) -> None:
        tree = self.query_one("#picker-tree", AudioFileTree)
        self.query_one("#picker-path", Static).update(str(tree.path))