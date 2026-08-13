"""The Transcriber TUI — Textual app wiring transcription + summarization."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    TextArea,
)

from . import transcribe as transcribe_mod
from . import summarize as summarize_mod
from . import config as config_mod
from . import export as export_mod
from .config import Config, ConfigError, EditorNotFoundError, load_config
from .picker import FilePickerScreen
from .prompts import PromptsError, PromptStore


class TranscriberApp(App):
    """TUI for transcribing audio and summarizing the result with an LLM."""

    TITLE = "transcriber-tui"
    SUB_TITLE = "local Whisper + LLM summarization"

    CSS = """
    Screen { background: $surface; }
    #main { padding: 1 2; }
    #file-row { height: 3; margin-bottom: 1; }
    #file-input { width: 1fr; }
    #meta-row { height: 1; margin-bottom: 1; color: $text-muted; }
    #button-row { height: 3; margin-bottom: 1; }
    #button-row Button { margin-right: 1; }
    #status { height: 1; color: $accent; }
    #loading { height: 1; }
    #content { height: 1fr; }
    #content Vertical { height: 1fr; border: solid $primary; margin-bottom: 1; }
    .pane-title { height: 1; background: $primary; color: $text; text-style: bold; padding: 0 1; }
    #transcript-area, #summary-area { height: 1fr; border: none; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "transcribe", "Transcribe"),
        Binding("s", "summarize", "Summarize"),
        Binding("e", "edit_prompt", "Edit Prompt"),
        Binding("r", "reload_prompts", "Reload Prompts"),
        Binding("c", "cycle_prompt", "Cycle Prompt"),
        Binding("b", "cycle_backend", "Cycle Backend"),
        Binding("o", "browse", "Browse File"),
        Binding("d", "edit_env", "Edit .env"),
        Binding("x", "export_markdown", "Export .md"),
        Binding("f", "run_full_workflow", "Full Workflow"),
    ]

    def __init__(self, audio_path: str | None = None) -> None:
        super().__init__()
        self._initial_path = audio_path
        self._transcript_text = ""
        self._summary_text = ""
        self._prompt_names: list[str] = []
        self._prompt_index = 0
        self._backends = ("openrouter", "ollama", "llamacpp", "lmstudio", "local")
        self._backend_index = 0
        self._working = False

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main"):
            with Horizontal(id="file-row"):
                yield Input(placeholder="Path to audio file", id="file-input")
                yield Button("Browse", id="browse-btn")
                yield Button("Transcribe", id="transcribe-btn", variant="primary")
                yield Button("Export .md", id="export-btn")
                yield Button("Full Workflow", id="full-workflow-btn", variant="success")
            yield Label("", id="meta-row")
            yield Label("", id="status")
            with Horizontal(id="loading"):
                yield LoadingIndicator(id="loading-ind")
                yield Label("", id="loading-text")
            with Vertical(id="content"):
                with Vertical(id="transcript-pane"):
                    yield Label("Transcript", classes="pane-title")
                    yield TextArea(id="transcript-area", read_only=True)
                with Vertical(id="summary-pane"):
                    yield Label("Summary", classes="pane-title")
                    yield TextArea(id="summary-area", read_only=True)
        yield Footer()

    def on_mount(self) -> None:
        self._loading(False)
        try:
            self._config: Config = load_config()
        except ConfigError as exc:
            self._status(str(exc))
            self._config = Config()
            return

        # Keep the B-key cycle index in sync with the backend loaded from
        # .env, so pressing B advances from the *actual* current backend
        # rather than always assuming it started on openrouter.
        if self._config.summarize_backend in self._backends:
            self._backend_index = self._backends.index(
                self._config.summarize_backend
            )

        self._store = PromptStore()
        try:
            self._store.load()
        except PromptsError as exc:
            self._status(str(exc).splitlines()[0])
        self._refresh_prompt_names()
        self._update_meta()

        if self._initial_path:
            self.query_one("#file-input", Input).value = self._initial_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _loading(self, active: bool, text: str = "") -> None:
        self.query_one("#loading-ind", LoadingIndicator).display = active
        self.query_one("#loading-text", Label).update(text)
        self._working = active

    def _status(self, text: str) -> None:
        self.query_one("#status", Label).update(text)

    def _refresh_prompt_names(self) -> None:
        """Rebuild the prompt name list and select the default/remembered one.

        Uses PromptStore.active_name() (meeting_summary by default, or the
        user's last explicit C-selection if one was persisted) rather than
        blindly picking index 0 of the alphabetically-sorted name list —
        that would land on "custom" (a placeholder, not a real prompt) on
        a fresh install, since "custom" sorts before every other name.
        """
        self._prompt_names = self._store.names() or ["custom"]
        active = self._store.active_name()
        self._prompt_index = (
            self._prompt_names.index(active) if active in self._prompt_names else 0
        )

    def _current_prompt(self) -> str:
        name = self._prompt_names[self._prompt_index]
        return self._store.get(name)

    def _update_meta(self) -> None:
        """Refresh the meta row: active prompt, backend, model, and Whisper size."""
        prompt = self._prompt_names[self._prompt_index]
        cfg = self._config
        self.query_one("#meta-row", Label).update(
            f"Prompt: {prompt}   |   Backend: {cfg.summarize_backend} "
            f"({cfg.summarize_model or '?'})   |   Whisper: {cfg.whisper_model}"
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_transcribe(self) -> None:
        if self._working:
            return
        path = self.query_one("#file-input", Input).value.strip()
        if not path or not Path(path).exists():
            self._status(f"File not found: {path or '(empty)'}")
            return

        self._status(f"Transcribing {os.path.basename(path)} ...")
        self._loading(True, "Transcribing ...")
        self.run_worker(
            lambda: self._do_transcribe(path), thread=True, exclusive=True
        )

    def _do_transcribe(self, path: str) -> None:
        """Runs in a worker thread (CPU-bound Whisper)."""
        try:
            result = transcribe_mod.transcribe(
                path, model_size=getattr(self._config, "whisper_model", "base")
            )
        except Exception as exc:  # noqa: BLE001 — surface any failure to the user
            self.call_from_thread(self._on_transcribe_error, exc)
            return
        self.call_from_thread(self._on_transcribe_done, result)

    def _on_transcribe_error(self, exc: Exception) -> None:
        self._loading(False)
        self._status(f"Transcription failed: {exc}")

    def _on_transcribe_done(self, result) -> None:
        self._loading(False)
        self._transcript_text = transcribe_mod.format_segments(result)
        self.query_one("#transcript-area", TextArea).text = self._transcript_text
        self._status(
            f"Transcribed in {result.duration:.1f}s of audio "
            f"({result.language}, {len(result.segments)} segments) — press S to summarize"
        )

    def action_summarize(self) -> None:
        if self._working:
            return
        if not self._transcript_text:
            self._status("No transcript yet — press T first")
            return

        cfg = self._config
        if cfg.uses_openrouter and not cfg.openrouter_api_key:
            self._status("Missing OPENROUTER_API_KEY — set it in .env (or cycle backend with B)")
            return

        prompt = self._current_prompt()
        self._summary_text = ""
        self.query_one("#summary-area", TextArea).text = ""
        self._status(f"Summarizing via {cfg.summarize_backend} ({cfg.summarize_model}) ...")
        self._loading(True, "Summarizing ...")
        self.run_worker(self._do_summarize(prompt), exclusive=True)

    async def _do_summarize(self, prompt: str) -> None:
        """Streams summary chunks into the TextArea (async), then auto-exports."""
        cfg = self._config
        try:
            async for chunk in summarize_mod.summarize(
                self._transcript_text,
                prompt,
                cfg.summarize_model,
                cfg.openrouter_api_key if cfg.uses_openrouter else "",
                cfg.summarize_base_url,
            ):
                self._summary_text += chunk
                self.query_one("#summary-area", TextArea).text = self._summary_text
        except Exception as exc:  # noqa: BLE001
            self._status(f"Summarization failed: {exc}")
            self._loading(False)
            return

        # Auto-export markdown after summarization completes.
        audio_path = self.query_one("#file-input", Input).value.strip()
        prompt_name = (
            self._prompt_names[self._prompt_index] if self._prompt_names else ""
        )
        content = export_mod.build_markdown(
            audio_path=audio_path,
            transcript_text=self._transcript_text,
            summary_text=self._summary_text,
            prompt_name=prompt_name,
            backend=cfg.summarize_backend,
            model=cfg.summarize_model,
            whisper_model=cfg.whisper_model,
        )
        export_dir = getattr(cfg, "export_dir", "") or None
        target = export_mod.default_export_path(audio_path, export_dir)
        try:
            saved_path = export_mod.save_markdown(content, target)
        except OSError as exc:
            self._loading(False)
            self._status(
                f"Summary complete ({len(self._summary_text)} chars) "
                f"but export failed: {exc} (press X to retry)"
            )
            return

        self._loading(False)
        self._status(
            f"Summary complete ({len(self._summary_text)} chars) "
            f"— exported to {saved_path}"
        )

    def action_edit_prompt(self) -> None:
        """Open the prompts file in $EDITOR, suspending the TUI meanwhile.

        Called directly (not via run_worker) because suspend() hands the
        terminal to the external editor and blocks until it exits — it is
        meant to run synchronously on the main thread, per Textual's own
        docs. Wrapping it in a worker thread would race the suspend/resume
        of driver state against the main event loop for no benefit.
        """
        if self._working:
            return
        try:
            editor = config_mod.resolve_editor()
        except EditorNotFoundError as exc:
            self._status(str(exc).splitlines()[0])
            return
        store = getattr(self, "_store", None) or PromptStore()
        store.ensure_exists()
        path = str(store.path)

        with self.suspend():
            subprocess.call(editor.split() + [path])
        try:
            store.reload()
        except PromptsError as exc:
            self._status(str(exc).splitlines()[0])
            return
        self._on_prompts_reloaded()

    def action_edit_env(self) -> None:
        """Open .env in $EDITOR, suspending the TUI meanwhile.

        Creates .env (seeded from .env.example) if none exists yet, so
        first-time setup — including OPENROUTER_API_KEY — never requires
        leaving the TUI.

        Called directly (not via run_worker) for the same reason as
        action_edit_prompt: suspend() is meant to run synchronously on the
        main thread while it hands the terminal to the external editor.
        """
        if self._working:
            return
        try:
            editor = config_mod.resolve_editor()
        except EditorNotFoundError as exc:
            self._status(str(exc).splitlines()[0])
            return
        path = str(config_mod.resolve_env_path())

        with self.suspend():
            subprocess.call(editor.split() + [path])
        self._on_env_reloaded()

    def _on_env_reloaded(self) -> None:
        """Re-read .env after the editor closes and apply it live."""
        try:
            self._config = load_config(reload=True)
        except ConfigError as exc:
            self._status(str(exc))
            return
        self._update_meta()
        self._status(
            f".env reloaded — backend: {self._config.summarize_backend} "
            f"({self._config.summarize_model or '?'})"
        )

    def action_reload_prompts(self) -> None:
        store = getattr(self, "_store", None) or PromptStore()
        try:
            store.reload()
        except PromptsError as exc:
            self._status(str(exc).splitlines()[0])
            return
        self._on_prompts_reloaded()

    def _on_prompts_reloaded(self) -> None:
        self._refresh_prompt_names()
        self._update_meta()
        self._status(f"Prompts reloaded ({len(self._prompt_names)} presets)")

    def action_cycle_prompt(self) -> None:
        if not self._prompt_names:
            return
        self._prompt_index = (self._prompt_index + 1) % len(self._prompt_names)
        selected = self._prompt_names[self._prompt_index]
        store = getattr(self, "_store", None)
        if store is not None:
            store.remember_selected(selected)
        self._update_meta()
        self._status(f"Prompt: {selected}")

    def action_cycle_backend(self) -> None:
        """Cycle the summarization backend: openrouter -> ollama -> llamacpp
        -> lmstudio -> local -> openrouter ...

        Resets summarize_model to a sensible per-backend default. For
        llamacpp/lmstudio/local there is no universal default model name;
        for lmstudio the loaded model is auto-detected from the server's
        /v1/models endpoint when possible. Otherwise set SUMMARIZE_MODEL
        (or the backend-specific *_MODEL env var) in .env, and the status
        bar will show "(?)" until you configure one.
        """
        self._backend_index = (self._backend_index + 1) % len(self._backends)
        backend = self._backends[self._backend_index]
        self._config.summarize_backend = backend
        self._config.summarize_base_url = config_mod.BACKEND_BASE_URLS.get(backend, "")
        # Set a sensible default model for each backend.
        defaults = {
            "openrouter": "deepseek/deepseek-v4-flash-0731",
            "ollama": "hermes-qwen35b:latest",
            "llamacpp": "",
            "lmstudio": "",
            "local": "",
        }
        model = defaults.get(backend, "")

        # Auto-detect the loaded model for LM Studio so the field isn't blank.
        if backend == "lmstudio" and not model:
            detected = self._detect_lmstudio_model()
            if detected:
                model = detected

        self._config.summarize_model = model
        self._update_meta()
        self._status(f"Backend: {backend}" + (f" ({model})" if model else ""))

    @staticmethod
    def _detect_lmstudio_model() -> str:
        """Query LM Studio's /v1/models endpoint for the loaded model name.

        Returns the first non-embedding model id, or "" if the server
        isn't reachable or returns nothing. Best-effort: failures leave
        the model field empty rather than blocking the backend switch.
        """
        import httpx

        try:
            resp = httpx.get("http://localhost:1234/v1/models", timeout=3.0)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            for item in data.get("data", []):
                model_id = item.get("id", "")
                if model_id and "embed" not in model_id.lower():
                    return model_id
        except Exception:  # noqa: BLE001 — best-effort detection
            return ""
        return ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "transcribe-btn":
            self.action_transcribe()
        elif event.button.id == "browse-btn":
            self.action_browse()
        elif event.button.id == "export-btn":
            self.action_export_markdown()
        elif event.button.id == "full-workflow-btn":
            self.action_run_full_workflow()

    def action_browse(self) -> None:
        """Open the file picker modal; set the input on selection."""
        start = Path.home()
        current = self.query_one("#file-input", Input).value.strip()
        if current:
            current_path = Path(current).expanduser()
            start = current_path if current_path.is_dir() else current_path.parent

        self.push_screen(FilePickerScreen(start), self._on_file_picked)

    def _on_file_picked(self, path: Path | None) -> None:
        if path is None:
            self._status("Browse cancelled")
            return
        self.query_one("#file-input", Input).value = str(path)
        self._status(f"Selected: {path}")

    def action_export_markdown(self) -> None:
        """Write the transcript + summary to a .md file next to the audio
        (or EXPORT_DIR from .env, if set) so they can be opened outside
        the TUI in any markdown viewer or editor.
        """
        if not self._transcript_text and not self._summary_text:
            self._status("Nothing to export yet — press T and/or S first")
            return

        audio_path = self.query_one("#file-input", Input).value.strip()
        cfg = self._config
        prompt_name = (
            self._prompt_names[self._prompt_index] if self._prompt_names else ""
        )

        content = export_mod.build_markdown(
            audio_path=audio_path,
            transcript_text=self._transcript_text,
            summary_text=self._summary_text,
            prompt_name=prompt_name,
            backend=getattr(cfg, "summarize_backend", ""),
            model=getattr(cfg, "summarize_model", ""),
            whisper_model=getattr(cfg, "whisper_model", ""),
        )

        export_dir = getattr(cfg, "export_dir", "") or None
        target = export_mod.default_export_path(audio_path, export_dir)
        try:
            saved_path = export_mod.save_markdown(content, target)
        except OSError as exc:
            self._status(f"Export failed: {exc}")
            return
        self._status(f"Exported to {saved_path}")

    def action_run_full_workflow(self) -> None:
        """Transcribe -> summarize -> export in one shot (F).

        The common workflow: point the file input at an audio file, then
        press F once instead of T, waiting, S, waiting, X. Runs as a
        single async worker so each stage's status/errors are reported
        as they happen, and a failure at any stage stops the chain
        (e.g. a failed transcription never gets summarized or exported)
        rather than silently producing a partial or garbage result.
        """
        if self._working:
            return
        path = self.query_one("#file-input", Input).value.strip()
        if not path or not Path(path).exists():
            self._status(f"File not found: {path or '(empty)'}")
            return

        cfg = self._config
        if cfg.uses_openrouter and not cfg.openrouter_api_key:
            self._status(
                "Missing OPENROUTER_API_KEY — set it in .env (or cycle backend with B)"
            )
            return

        self.run_worker(self._do_full_workflow(path), exclusive=True)

    async def _do_full_workflow(self, path: str) -> None:
        """Transcribe, then summarize, then export — stops on the first failure."""
        self._status(f"[1/3] Transcribing {os.path.basename(path)} ...")
        self._loading(True, "Transcribing ...")
        try:
            result = await asyncio.to_thread(
                transcribe_mod.transcribe,
                path,
                model_size=getattr(self._config, "whisper_model", "base"),
            )
        except Exception as exc:  # noqa: BLE001
            self._loading(False)
            self._status(f"Full workflow stopped — transcription failed: {exc}")
            return

        self._transcript_text = transcribe_mod.format_segments(result)
        self.query_one("#transcript-area", TextArea).text = self._transcript_text
        self._status(
            f"[2/3] Transcribed {result.duration:.1f}s of audio — summarizing ..."
        )

        prompt = self._current_prompt()
        self._summary_text = ""
        self.query_one("#summary-area", TextArea).text = ""
        cfg = self._config
        try:
            async for chunk in summarize_mod.summarize(
                self._transcript_text,
                prompt,
                cfg.summarize_model,
                cfg.openrouter_api_key if cfg.uses_openrouter else "",
                cfg.summarize_base_url,
            ):
                self._summary_text += chunk
                self.query_one("#summary-area", TextArea).text = self._summary_text
        except Exception as exc:  # noqa: BLE001
            self._loading(False)
            self._status(
                f"Full workflow stopped — summarization failed: {exc} "
                "(transcript was saved to the Transcript pane; press X to export it alone)"
            )
            return

        self._status("[3/3] Exporting markdown ...")
        prompt_name = (
            self._prompt_names[self._prompt_index] if self._prompt_names else ""
        )
        content = export_mod.build_markdown(
            audio_path=path,
            transcript_text=self._transcript_text,
            summary_text=self._summary_text,
            prompt_name=prompt_name,
            backend=cfg.summarize_backend,
            model=cfg.summarize_model,
            whisper_model=cfg.whisper_model,
        )
        export_dir = getattr(cfg, "export_dir", "") or None
        target = export_mod.default_export_path(path, export_dir)
        try:
            saved_path = export_mod.save_markdown(content, target)
        except OSError as exc:
            self._loading(False)
            self._status(
                f"Transcribed and summarized, but export failed: {exc} "
                "(press X to retry once fixed)"
            )
            return

        self._loading(False)
        self._status(f"Done — transcribed, summarized, and exported to {saved_path}")


def run(audio_path: str | None = None) -> None:
    """Entry point for the console_script and `python -m transcriber`."""
    TranscriberApp(audio_path).run()