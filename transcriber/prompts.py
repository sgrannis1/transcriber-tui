"""Prompt store: load/save/reload named summarization prompts from YAML.

Prompts are stored in `~/.config/transcriber/prompts.yaml` (XDG).
On first run, defaults are copied there from the package's shipped `prompts.yaml`.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

# Default prompts shipped in the repo; copied to user config on first run.
SHIPPED_PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts.yaml"

# User's persistent config (XDG convention).
USER_CONFIG_DIR = Path.home() / ".config" / "transcriber"
USER_PROMPTS_PATH = USER_CONFIG_DIR / "prompts.yaml"

# Remembers which prompt preset was last active, across restarts. Separate
# tiny file (not part of prompts.yaml) so it never shows up as a "prompt"
# and never gets clobbered by editing prompts.yaml by hand.
LAST_PROMPT_PATH = USER_CONFIG_DIR / "last_prompt.txt"

# Preferred default prompt on a brand-new install (before the user has ever
# picked one). Falls back to alphabetical-first if this name isn't present.
DEFAULT_PROMPT_NAME = "meeting_summary"

# --- Default prompts embedded as a fallback (matches shipped prompts.yaml) ---
_DEFAULTS: dict[str, str] = {
    "meeting_summary": (
        "You are a meeting assistant. Summarize this transcript with: "
        "## Summary (2-3 sentences), ## Key Points (bullets), "
        "## Action Items (with owners if mentioned), ## Decisions. Be concise."
    ),
    "lecture_notes": (
        "You are a study assistant. Convert this lecture transcript into organized notes: "
        "## Main Concepts, ## Key Terms, ## Examples, ## Questions to follow up on."
    ),
    "quick_recap": (
        "You are a recapper. Give a 3-bullet recap of this transcript in plain language. No headers."
    ),
    "custom": (
        "Paste your own summarization instructions here. "
        "This is the one you edit over time for your specific needs."
    ),
}


class PromptStore:
    """Load, save, reload, and enumerate named summarization prompts."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or USER_PROMPTS_PATH
        self.prompts: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def ensure_exists(self) -> None:
        """Create the prompts file from defaults if it does not exist."""
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if SHIPPED_PROMPTS_PATH.exists():
            shutil.copy2(SHIPPED_PROMPTS_PATH, self.path)
        else:
            self._write(_DEFAULTS)
        self.prompts = dict(_DEFAULTS)  # seed in-memory copy

    def load(self) -> dict[str, str]:
        """Load prompts from disk. If the file is missing, create it first."""
        self.ensure_exists()
        with open(self.path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        # Coerce values to strings (safe_load may leave them as Any).
        self.prompts = {str(k): str(v) for k, v in raw.items() if v}
        if not self.prompts:
            self.prompts = dict(_DEFAULTS)
        return self.prompts

    def reload(self) -> dict[str, str]:
        """Re-read from disk (call after external edit in $EDITOR)."""
        return self.load()

    def save(self, prompts: dict[str, str] | None = None) -> None:
        """Write current prompts to disk."""
        if prompts is not None:
            self.prompts = dict(prompts)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write(self.prompts)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, name: str) -> str:
        """Return a single prompt by name (empty string if missing)."""
        return self.prompts.get(name, "")

    def names(self) -> list[str]:
        """Return sorted prompt names."""
        return sorted(self.prompts.keys())

    def active_name(self) -> str:
        """Return the prompt to activate by default.

        Priority: the user's last explicit selection (persisted across
        restarts) > the built-in DEFAULT_PROMPT_NAME (meeting_summary) if
        present > alphabetically first as a last resort.
        """
        names = self.names()
        if not names:
            return "custom"

        last = self._read_last_selected()
        if last and last in names:
            return last

        if DEFAULT_PROMPT_NAME in names:
            return DEFAULT_PROMPT_NAME

        return names[0]

    def remember_selected(self, name: str) -> None:
        """Persist the given prompt name as the "last selected" for next launch."""
        try:
            LAST_PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
            LAST_PROMPT_PATH.write_text(name, encoding="utf-8")
        except OSError:
            pass  # best-effort; never let persistence failures break the TUI

    def _read_last_selected(self) -> str:
        try:
            return LAST_PROMPT_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def edit_with_editor(self, editor: str | None = None) -> int:
        """Open the prompts file in $EDITOR. Returns the subprocess exit code."""
        editor = editor or "vim"
        # Textual apps should suspend before calling this; outside Textual
        # (standalone) the editor takes over the terminal directly.
        return subprocess.call([editor, str(self.path)])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write(self, data: dict[str, str]) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, default_flow_style=False)