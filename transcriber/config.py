"""Configuration loading: env vars, model size, and paths."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .prompts import USER_CONFIG_DIR, USER_PROMPTS_PATH

DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
DEFAULT_WHISPER_MODEL = "base"
VALID_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3")


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


@dataclass
class Config:
    """Resolved runtime configuration."""

    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_MODEL
    whisper_model: str = DEFAULT_WHISPER_MODEL
    config_dir: Path = field(default_factory=lambda: USER_CONFIG_DIR)
    prompts_path: Path = field(default_factory=lambda: USER_PROMPTS_PATH)


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


def load_config() -> Config:
    """Load configuration from .env and environment variables.

    Raises ConfigError if OPENROUTER_API_KEY is missing (clear message,
    not a traceback).
    """
    env_file = _find_env_file()
    if env_file is not None:
        load_dotenv(env_file, override=False)

    cfg = Config(
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        openrouter_model=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
        whisper_model=os.environ.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL),
    )

    if not cfg.openrouter_api_key:
        raise ConfigError(
            "OPENROUTER_API_KEY is not set.\n"
            "Copy .env.example to .env and set OPENROUTER_API_KEY, or export it:\n"
            "  export OPENROUTER_API_KEY=<your-key>\n"
            "Get a key at https://openrouter.ai/keys"
        )

    if cfg.whisper_model not in VALID_WHISPER_MODELS:
        raise ConfigError(
            f"Invalid WHISPER_MODEL '{cfg.whisper_model}'. "
            f"Choose from: {', '.join(VALID_WHISPER_MODELS)}"
        )

    return cfg