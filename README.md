# transcriber-tui

A Textual TUI that transcribes audio files with local [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and summarizes the transcript with an LLM via [OpenRouter](https://openrouter.ai).

**Zero transcription cost** — Whisper runs locally on CPU. Summarization uses your OpenRouter key or a local model (Ollama / llama.cpp).

## Features

- Transcribe any audio file with local Whisper (225x realtime on CPU with the `base` model)
- Summarize with **OpenRouter** (cloud) or **local models** via Ollama / llama.cpp / any OpenAI-compatible endpoint
- Stream summaries from an LLM with live token display
- Cycle backends at runtime with `B` — switch between cloud and local models without restarting
- Editable summarization prompts — press `E` to open in vim, save, and reload
- Multiple prompt presets (meeting summary, lecture notes, quick recap, custom)
- All configuration lives in plain text files — no databases, no cloud

## Quick Start

```bash
# Clone and set up
git clone git@github.com:sgrannis1/transcriber-tui.git
cd transcriber-tui
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Configure your OpenRouter API key
cp .env.example .env
# Edit .env and set: OPENROUTER_API_KEY=<your-key>
# Get a key at https://openrouter.ai/keys

# Launch
python -m transcriber /path/to/audio.mp3
```

On first run, Whisper downloads the `base` model (~142MB) to `~/.cache/huggingface`. This happens once.

## Keyboard Reference

| Key | Action |
|-----|--------|
| `T` | Transcribe the selected audio file |
| `S` | Summarize the transcript |
| `B` | Cycle summarization backend (openrouter → ollama → llamacpp → local) |
| `E` | Edit prompts in `$EDITOR` (default: vim) |
| `R` | Reload prompts from disk |
| `C` | Cycle to the next prompt preset |
| `Q` | Quit |

## Summarization Backends

The summarizer supports multiple backends, cycled at runtime with `B` or set via `.env`:

| Backend | Default URL | Model env var | Auth |
|---------|-------------|---------------|------|
| `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_MODEL` | `OPENROUTER_API_KEY` |
| `ollama` | `http://localhost:11434/v1` | `OLLAMA_MODEL` | none |
| `llamacpp` | `http://localhost:8080/v1` | `LLAMACPP_MODEL` | none |
| `local` | `http://localhost:11434/v1`* | `LOCAL_MODEL` | none |

*Override with `SUMMARIZE_BASE_URL` for any OpenAI-compatible endpoint (LM Studio, vLLM, etc.).

Set `SUMMARIZE_BACKEND` in `.env` to pick the default, and `SUMMARIZE_MODEL` for the model name. For Ollama, you can also set `OLLAMA_MODEL` as shorthand:

## Prompt Presets

Prompts live in `~/.config/transcriber/prompts.yaml` (created automatically on first run from the shipped `prompts.yaml`). Edit them in vim by pressing `E` in the TUI, or edit the file directly and press `R` to reload.

Built-in presets: `meeting_summary`, `lecture_notes`, `quick_recap`, and `custom` (the "edit-over-time" prompt).

## Configuration

All settings via environment or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUMMARIZE_BACKEND` | `openrouter` | Backend: `openrouter`, `ollama`, `llamacpp`, or `local` |
| `SUMMARIZE_MODEL` | *(backend-dependent)* | Model name for the active summarization backend |
| `SUMMARIZE_BASE_URL` | *(backend-dependent)* | Override the default base URL for any backend |
| `OPENROUTER_API_KEY` | *(required for openrouter)* | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `deepseek/deepseek-v4-flash-0731` | Cloud LLM model (openrouter backend) |
| `OLLAMA_MODEL` | `hermes-qwen35b:latest` | Local model name (ollama backend) |
| `LLAMACPP_MODEL` | *(empty)* | Local model name (llamacpp backend) |
| `WHISPER_MODEL` | `base` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `EDITOR` | `vim` | Text editor for prompt editing |

## Architecture

```
transcriber/
├── app.py          # Textual TUI (layout, bindings, worker flows)
├── config.py       # .env loading and Config dataclass
├── prompts.py      # PromptStore — YAML load/save/reload
├── transcribe.py   # faster-whisper wrapper (thread-safe model cache)
├── summarize.py    # OpenRouter streaming summarization
├── __main__.py     # `python -m transcriber` entry point
└── __init__.py
```

Transcription runs in a worker thread (CPU-bound), summarization runs as an async generator that streams tokens into the TUI live.

## License

MIT