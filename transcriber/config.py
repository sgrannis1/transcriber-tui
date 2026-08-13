"""Configuration loading: env vars, model size, paths, and summarization backend."""
from __future__ import annotations

import os
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


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


@dataclass
class Config:
    """Resolved runtime configuration."""

    summarize_backend: str = "openrouter"
    openrouter_api_key: str = ""
    summarize_model: str = DEFAULT_OPENROUTER_MODEL
    summarize_base_url: str = _BACKEND_BASE_URLS["openrouter"]
    whisper_model: str = DEFAULT_WHISPER_MODEL
    config_dir: Path = field(default_factory=lambda: USER_CONFIG_DIR)
    prompts_path: Path = field(default_factory=lambda: USER_PROMPTS_PATH)

    @property
    def uses_openrouter(self) -> bool:
        return self.summarize_backend == "openrouter"


def _find_env_file() -> Path | None:
    """Locate the .env file: project root first, then home."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path.home() / ".hermes" / ".env",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def _resolve_backend(raw: str) -> str:
    """Normalise the backend name to one of the recognised values."""
    backend = raw.strip().lower()
    if backend in VALID_BACKENDS:
        return backend
    raise ConfigError(
        f"Unknown SUMMARIZE_BACKEND '{raw}'. "
        f"Choose from: {', '.join(VALID_BACKENDS)}"
    )


def load_config() -> Config:
    """Load configuration from .env and environment variables.

    Raises ConfigError on invalid or missing required values (with a clear
    message, never a bare traceback).
    """
    env_file = _find_env_file()
    if env_file is not None:
        load_dotenv(env_file, override=False)

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
    )

    if cfg.uses_openrouter and not cfg.openrouter_api_key:
        raise ConfigError(
            "OPENROUTER_API_KEY is not set, but SUMMARIZE_BACKEND is 'openrouter'.\n"
            "Either set OPENROUTER_API_KEY in .env, or set SUMMARIZE_BACKEND to a\n"
            "local backend (ollama / llamacpp / lmstudio / local)."
        )

    if cfg.whisper_model not in VALID_WHISPER_MODELS:
        raise ConfigError(
            f"Invalid WHISPER_MODEL '{cfg.whisper_model}'. "
            f"Choose from: {', '.join(VALID_WHISPER_MODELS)}"
        )

    return cfg