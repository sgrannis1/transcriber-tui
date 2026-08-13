"""Configuration loading: env vars, model size, paths, and summarization backend."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from .prompts import USER_CONFIG_DIR, USER_PROMPTS_PATH

DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4-flash-0731"
DEFAULT_WHISPER_MODEL = "base"
VALID_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3")

# Recognised summarization backends.
SummarizeBackend = Literal["openrouter", "ollama", "llamacpp", "lmstudio", "local"]
VALID_BACKENDS = ("openrouter", "ollama", "llamacpp", "lmstudio", "local")

# Editors tried, in order, when $EDITOR is unset or points at something
# that isn't actually installed. Covers the common case on minimal Linux
# installs where vim isn't present but nano or vi (POSIX-mandated) is.
FALLBACK_EDITORS = ("nano", "vi", "vim", "emacs")

# Default base URLs for each backend.
BACKEND_BASE_URLS: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "llamacpp": "http://localhost:8080/v1",
    "lmstudio": "http://localhost:1234/v1",
    "local": "http://localhost:11434/v1",
}
# Backwards-compatible alias (old private name); prefer BACKEND_BASE_URLS.
_BACKEND_BASE_URLS = BACKEND_BASE_URLS


# Prefixes of API keys from *other* providers that are easy to paste into
# OPENROUTER_API_KEY by mistake (e.g. copying from a different .env). Used
# only to produce a clear, specific error instead of a confusing 401 from
# OpenRouter itself ("Missing Authentication header", which does not
# mention that a key was actually sent -- just the wrong kind).
_KNOWN_OTHER_KEY_PREFIXES: dict[str, str] = {
    "sk-proj-": "an OpenAI (not OpenRouter)",
    "sk-ant-": "an Anthropic",
}
# OpenRouter keys always start with this prefix.
_OPENROUTER_KEY_PREFIX = "sk-or-"


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


class EditorNotFoundError(RuntimeError):
    """Raised when no usable text editor can be found on the system."""


@dataclass
class Config:
    """Resolved runtime configuration."""

    summarize_backend: str = "openrouter"
    openrouter_api_key: str = ""
    summarize_model: str = DEFAULT_OPENROUTER_MODEL
    summarize_base_url: str = _BACKEND_BASE_URLS["openrouter"]
    whisper_model: str = DEFAULT_WHISPER_MODEL
    export_dir: str = ""
    config_dir: Path = field(default_factory=lambda: USER_CONFIG_DIR)
    prompts_path: Path = field(default_factory=lambda: USER_PROMPTS_PATH)

    @property
    def uses_openrouter(self) -> bool:
        return self.summarize_backend == "openrouter"


def _find_env_file() -> Path | None:
    """Locate an existing .env file: cwd first, then project root, then ~/.hermes."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path.home() / ".hermes" / ".env",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def resolve_editor() -> str:
    """Resolve a text editor command that actually exists on this system.

    A bare "vim" default (as older versions of this app used) fails with
    a raw FileNotFoundError on any system where vim isn't installed --
    which is common on minimal Linux setups where only nano or the
    POSIX-mandated vi ships by default. This checks, in order:

      1. $EDITOR, if set AND the command it names is actually on PATH
         (an $EDITOR pointing at something missing is treated the same
         as $EDITOR being unset, rather than blindly trusted)
      2. Each name in FALLBACK_EDITORS, in order, that resolves via PATH
      3. Raises EditorNotFoundError with actionable guidance if nothing
         above is found, instead of letting subprocess raise a bare
         FileNotFoundError with no context.

    Only the first whitespace-separated token of $EDITOR is checked
    against PATH (e.g. "code --wait" -> checks for "code"); the full
    string is still what gets passed to subprocess so editor flags work.
    """
    editor_env = os.environ.get("EDITOR", "").strip()
    if editor_env:
        command = editor_env.split()[0]
        if shutil.which(command):
            return editor_env
        # $EDITOR is set but not installed/found -- fall through to the
        # fallback list rather than pass a command that will just fail.

    for candidate in FALLBACK_EDITORS:
        if shutil.which(candidate):
            return candidate

    raise EditorNotFoundError(
        "No text editor found. None of "
        f"{', '.join(FALLBACK_EDITORS)} are on PATH"
        + (f", and $EDITOR='{editor_env}' is not either" if editor_env else "")
        + ".\nInstall one (e.g. `sudo apt install nano`) or set EDITOR to "
        "a command that exists, e.g.:\n  export EDITOR=nano"
    )


def resolve_env_path() -> Path:
    """Return the .env path to use for editing, creating one if none exists.

    If an .env already exists (see _find_env_file's search order), that
    exact file is returned so edits land where load_config() actually
    reads from. Otherwise a new .env is created next to the project's
    .env.example (seeded from it when present) so there is always a
    single, predictable file to edit.
    """
    existing = _find_env_file()
    if existing is not None:
        return existing

    project_root = Path(__file__).resolve().parent.parent
    new_env = project_root / ".env"
    example = project_root / ".env.example"
    if example.exists():
        import shutil

        shutil.copy2(example, new_env)
    else:
        new_env.write_text("OPENROUTER_API_KEY=\n", encoding="utf-8")
    return new_env


def _resolve_backend(raw: str) -> str:
    """Normalise the backend name to one of the recognised values."""
    backend = raw.strip().lower()
    if backend in VALID_BACKENDS:
        return backend
    raise ConfigError(
        f"Unknown SUMMARIZE_BACKEND '{raw}'. "
        f"Choose from: {', '.join(VALID_BACKENDS)}"
    )


def _validate_openrouter_key_format(key: str) -> None:
    """Catch the common "wrong provider's key" mistake before it ever
    reaches OpenRouter and comes back as a confusing generic 401.

    OpenRouter itself replies "Missing Authentication header" for a key
    it can't recognise as one of its own -- which reads as if no key was
    sent at all, even though one was. Checking the prefix locally turns
    that into an immediate, specific, actionable error.
    """
    for prefix, provider in _KNOWN_OTHER_KEY_PREFIXES.items():
        if key.startswith(prefix):
            raise ConfigError(
                f"OPENROUTER_API_KEY looks like {provider} key "
                f"(starts with '{prefix}'), not an OpenRouter key.\n"
                f"OpenRouter keys start with '{_OPENROUTER_KEY_PREFIX}'.\n"
                "Get a real OpenRouter key at https://openrouter.ai/keys "
                "and set it in .env (press D in the TUI to edit it)."
            )
    if not key.startswith(_OPENROUTER_KEY_PREFIX):
        # Not a known other-provider prefix either -- warn but don't hard
        # fail, since OpenRouter's key format could change or this could
        # be a legitimate edge case (e.g. a proxy/gateway in front of it).
        # A ConfigError here would be too aggressive; let the real request
        # be the final judge, but the shape is unusual enough to be worth
        # noting in case it explains a downstream 401.
        pass


def load_config(*, reload: bool = False) -> Config:
    """Load configuration from .env and environment variables.

    Raises ConfigError on invalid or missing required values (with a clear
    message, never a bare traceback).

    Pass reload=True after the user has edited .env mid-session (e.g. via
    the in-TUI editor): python-dotenv normally refuses to overwrite
    variables already present in os.environ, which would make edits to an
    already-loaded key invisible until the process restarts. reload=True
    forces the newly-edited file to win.
    """
    env_file = _find_env_file()
    if env_file is not None:
        load_dotenv(env_file, override=reload)

    backend = _resolve_backend(
        os.environ.get("SUMMARIZE_BACKEND", "openrouter")
    )

    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    # Determine base URL: explicit SUMMARIZE_BASE_URL overrides the default.
    base_url = os.environ.get(
        "SUMMARIZE_BASE_URL", BACKEND_BASE_URLS.get(backend, "")
    ).rstrip("/")

    # Determine model: explicit SUMMARIZE_MODEL overrides backend's default.
    model = os.environ.get("SUMMARIZE_MODEL")
    if not model:
        if backend == "openrouter":
            model = os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        elif backend == "ollama":
            model = os.environ.get("OLLAMA_MODEL", "hermes-qwen35b:latest")
        elif backend == "llamacpp":
            model = os.environ.get("LLAMACPP_MODEL", "")
        elif backend == "lmstudio":
            model = os.environ.get("LMSTUDIO_MODEL", "")
        else:
            model = os.environ.get("LOCAL_MODEL", "")

    if not model:
        raise ConfigError(
            f"SUMMARIZE_MODEL is required for backend '{backend}'.\n"
            "Set SUMMARIZE_MODEL=... in your .env file."
        )

    cfg = Config(
        summarize_backend=backend,
        openrouter_api_key=api_key,
        summarize_model=model,
        summarize_base_url=base_url,
        whisper_model=os.environ.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL),
        export_dir=os.environ.get("EXPORT_DIR", ""),
    )

    if cfg.uses_openrouter and not cfg.openrouter_api_key:
        raise ConfigError(
            "OPENROUTER_API_KEY is not set, but SUMMARIZE_BACKEND is 'openrouter'.\n"
            "Either set OPENROUTER_API_KEY in .env, or set SUMMARIZE_BACKEND to a\n"
            "local backend (ollama / llamacpp / lmstudio / local)."
        )

    if cfg.uses_openrouter and cfg.openrouter_api_key:
        _validate_openrouter_key_format(cfg.openrouter_api_key)

    if cfg.whisper_model not in VALID_WHISPER_MODELS:
        raise ConfigError(
            f"Invalid WHISPER_MODEL '{cfg.whisper_model}'. "
            f"Choose from: {', '.join(VALID_WHISPER_MODELS)}"
        )

    return cfg