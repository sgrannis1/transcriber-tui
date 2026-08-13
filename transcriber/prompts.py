"""Prompt store: one markdown file per prompt type.

Prompts are stored as individual ``.md`` files under
``~/.config/transcriber/prompts/`` (XDG).  On first run the directory is
seeded from built-in defaults.  An existing legacy ``prompts.yaml`` (the
pre-1.0 single-file format) is migrated automatically — each key becomes
``{name}.md`` and the old file is renamed so it is never read again.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


class PromptsError(RuntimeError):
    """Raised when a prompt file cannot be read."""


# ---------------------------------------------------------------------------
# Paths (XDG convention)
# ---------------------------------------------------------------------------

USER_CONFIG_DIR = Path.home() / ".config" / "transcriber"

# Directory holding one ``.md`` file per prompt.
USER_PROMPTS_DIR = USER_CONFIG_DIR / "prompts"

# Remembers which prompt preset was last active across restarts.
LAST_PROMPT_PATH = USER_CONFIG_DIR / "last_prompt.txt"

# Preferred default prompt on a brand-new install.
DEFAULT_PROMPT_NAME = "meeting_summary"

# Filesystem-safe name for the always-present custom scratchpad prompt.
_CUSTOM_NAME = "custom"

# All recognised prompt names — used to seed the directory and to decide
# which names are "known" when enumerating (extra files on disk are also
# picked up so the user can drop in new ones).
_BUILTIN_NAMES: tuple[str, ...] = (
    "meeting_summary",
    "lecture_notes",
    "quick_recap",
    _CUSTOM_NAME,
)


# ---------------------------------------------------------------------------
# Built-in default prompt text
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, str] = {
    "meeting_summary": (
        "You are a meeting assistant. Summarize this transcript with: "
        "## Summary (2-3 sentences), ## Key Points (bullets), "
        "## Action Items (with owners if mentioned), ## Decisions. "
        "Be concise."
    ),
    "lecture_notes": (
        "You are a study assistant. Convert this lecture transcript "
        "into organised notes: ## Main Concepts, ## Key Terms, "
        "## Examples, ## Questions to follow up on."
    ),
    "quick_recap": (
        "You are a recapper. Give a 3-bullet recap of this transcript "
        "in plain language. No headers."
    ),
    _CUSTOM_NAME: (
        "Paste your own summarization instructions here. "
        "This is the one you edit over time for your specific needs."
    ),
}


# ====================================================================
# PromptStore
# ====================================================================


class PromptStore:
    """Load, reload, and enumerate per-file summarization prompts."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or USER_PROMPTS_DIR
        self.prompts: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def ensure_exists(self) -> None:
        """Create the prompts directory and seed any missing built-in files.

        If a legacy ``prompts.yaml`` exists it is migrated into the
        directory automatically and then renamed out of the way.
        """
        self._maybe_migrate()
        self._dir.mkdir(parents=True, exist_ok=True)
        for name in _BUILTIN_NAMES:
            path = self._path_for(name)
            if not path.exists():
                path.write_text(_DEFAULTS.get(name, ""), encoding="utf-8")

    def load(self) -> dict[str, str]:
        """Read every ``.md`` file from the prompts directory.

        On first call, seeds the directory from built-in defaults (and
        migrates any legacy ``prompts.yaml`` if it exists).  Built-in
        names that still have no file on disk after seeding are
        back-filled from the embedded defaults so the TUI never shows
        an empty prompt list.
        """
        self.ensure_exists()
        return self._read_from_disk()

    def reload(self) -> dict[str, str]:
        """Re-read from disk (call after editing a prompt file).

        Does *not* recreate deleted built-in files — just re-reads
        whatever ``.md`` files currently exist on disk.
        """
        self.prompts.clear()
        # Still check for a legacy YAML that appeared since last load.
        self._maybe_migrate()
        return self._read_from_disk(backfill_builtins=False)

    def _read_from_disk(
        self, backfill_builtins: bool = True
    ) -> dict[str, str]:
        """Scan the prompts directory and cache every ``.md`` file."""
        prompts: dict[str, str] = {}

        for path in sorted(self._dir.glob("*.md")):
            name = path.stem
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise PromptsError(
                    f"Cannot read prompt file {path}: {exc}"
                ) from exc
            if text.strip():
                prompts[name] = text

        # Back-fill built-in names not found on disk (only during
        # fresh load, not on reload — the user may have intentionally
        # deleted a file and we shouldn't silently resurrect it).
        if backfill_builtins:
            for name in _BUILTIN_NAMES:
                if name not in prompts:
                    prompts[name] = _DEFAULTS.get(name, "")

        self.prompts = prompts
        return self.prompts

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, name: str) -> str:
        """Return a single prompt's text (empty string if unknown)."""
        # Lazy-load the file if it hasn't been cached yet.
        if name not in self.prompts:
            path = self._path_for(name)
            if path.exists():
                try:
                    self.prompts[name] = path.read_text(encoding="utf-8")
                except OSError:
                    return ""
            else:
                return _DEFAULTS.get(name, "")
        return self.prompts.get(name, "")

    def names(self) -> list[str]:
        """Return sorted prompt names."""
        return sorted(self.prompts.keys())

    def active_name(self) -> str:
        """Return the prompt to activate by default.

        Priority: last explicit selection (persisted) >
        ``DEFAULT_PROMPT_NAME`` if present > alphabetically first.
        """
        names = self.names()
        if not names:
            return _CUSTOM_NAME

        last = self._read_last_selected()
        if last and last in names:
            return last

        if DEFAULT_PROMPT_NAME in names:
            return DEFAULT_PROMPT_NAME

        return names[0]

    def remember_selected(self, name: str) -> None:
        """Persist *name* as the last-selected prompt for next launch."""
        try:
            LAST_PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
            LAST_PROMPT_PATH.write_text(name, encoding="utf-8")
        except OSError:
            pass  # best-effort

    # ------------------------------------------------------------------
    # File paths
    # ------------------------------------------------------------------

    def file_for(self, name: str) -> Path:
        """Return the ``.md`` file path for *name*."""
        return self._path_for(name)

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def edit_with_editor(
        self, name: str, editor: str | None = None
    ) -> int:
        """Open the prompt file for *name* in ``$EDITOR``.

        Returns the subprocess exit code.  If no *editor* is given,
        resolves one via ``config.resolve_editor()``.
        """
        if editor is None:
            from . import config as config_mod  # local: avoids circ import

            editor = config_mod.resolve_editor()
        path = str(self.file_for(name))
        return subprocess.call(editor.split() + [path])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _path_for(self, name: str) -> Path:
        return self._dir / f"{name}.md"

    @staticmethod
    def _read_last_selected() -> str:
        try:
            return LAST_PROMPT_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    # ------------------------------------------------------------------
    # Migration from the pre-1.0 single-YAML-file format
    # ------------------------------------------------------------------

    def _maybe_migrate(self) -> None:
        """If a legacy ``prompts.yaml`` exists alongside the prompts
        directory, split it into individual ``.md`` files and rename
        it away so it is never read again."""
        old = self._dir.parent / "prompts.yaml"
        if not old.exists():
            return
        if self._dir.exists():
            # Directory already exists — don't risk overwriting newer
            # files.  Just rename the old file so it isn't re-read.
            _rename_away(old)
            return

        # Read the old YAML file.
        try:
            raw = yaml.safe_load(old.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            # Can't parse — seed from defaults and move the broken file
            # aside so we don't keep failing on every load.
            self._dir.mkdir(parents=True, exist_ok=True)
            for name in _BUILTIN_NAMES:
                (self._dir / f"{name}.md").write_text(
                    _DEFAULTS.get(name, ""), encoding="utf-8"
                )
            _rename_away(old)
            return

        # Write each old prompt into its own ``.md`` file.
        self._dir.mkdir(parents=True, exist_ok=True)
        for key, value in raw.items():
            name = str(key)
            text = str(value) if value else ""
            (self._dir / f"{name}.md").write_text(text, encoding="utf-8")

        # Ensure the built-in names exist (some may have been missing).
        for name in _BUILTIN_NAMES:
            path = self._dir / f"{name}.md"
            if not path.exists():
                path.write_text(_DEFAULTS.get(name, ""), encoding="utf-8")

        _rename_away(old)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _rename_away(path: Path) -> None:
    """Rename *path* so it is never read again."""
    target = path.with_suffix(path.suffix + ".migrated")
    try:
        shutil.move(str(path), str(target))
    except OSError:
        pass  # best-effort