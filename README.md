# transcriber-tui

A Textual TUI that transcribes audio files with local [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and summarizes the transcript with an LLM — via [OpenRouter](https://openrouter.ai) in the cloud, or a local model through Ollama, llama.cpp, LM Studio, or any OpenAI-compatible server.

**Zero transcription cost** — Whisper runs locally on CPU. Summarization uses your OpenRouter key or a local model (Ollama / llama.cpp / LM Studio).

## Features

- Transcribe any audio file with local Whisper (225x realtime on CPU with the `base` model)
- Built-in file browser — launch with no args and navigate to your audio in the TUI
- Summarize with **OpenRouter** (cloud) or **local models** via Ollama / llama.cpp / LM Studio / any OpenAI-compatible endpoint
- Stream summaries from an LLM with live token display
- Cycle backends at runtime with `B` — switch between cloud and local models without restarting
- Editable summarization prompts — press `E` to open in vim, save, and reload
- Edit `.env` (API key, backend, model) directly from the TUI with `D` — no manual file hunting
- Multiple prompt presets (meeting summary, lecture notes, quick recap, custom)
- All configuration lives in plain text files — no databases, no cloud

## Quick Start

```bash
# Clone and set up
git clone git@github.com:sgrannis1/transcriber-tui.git
cd transcriber-tui
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Launch — no args needed, browse to your file in the TUI
python -m transcriber

# First time only: press D inside the TUI to open/create .env in $EDITOR
# and set OPENROUTER_API_KEY (get one at https://openrouter.ai/keys), or
# do it from the shell instead:
cp .env.example .env
# Edit .env and set: OPENROUTER_API_KEY=<your-key>

# Or pass an audio file directly:
python -m transcriber /path/to/audio.mp3
```

On first run, Whisper downloads the `base` model (~142MB) to `~/.cache/huggingface`. This happens once.

## Keyboard Reference

| Key | Action |
|-----|--------|
| `T` | Transcribe the selected audio file |
| `O` | Browse for an audio file (file picker) |
| `S` | Summarize the transcript |
| `B` | Cycle summarization backend (openrouter → ollama → llamacpp → lmstudio → local) |
| `E` | Edit prompts in `$EDITOR` (default: vim) |
| `D` | Edit `.env` in `$EDITOR` — creates it from `.env.example` if missing |
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
| `lmstudio` | `http://localhost:1234/v1` | `LMSTUDIO_MODEL` | none |
| `local` | `http://localhost:11434/v1`* | `LOCAL_MODEL` | none |

*Override with `SUMMARIZE_BASE_URL` for any OpenAI-compatible endpoint (LM Studio, vLLM, etc.).

Set `SUMMARIZE_BACKEND` in `.env` to pick the startup default. Set `SUMMARIZE_MODEL` to name the model explicitly, or use the backend-specific shorthand (`OLLAMA_MODEL`, `LLAMACPP_MODEL`, `LMSTUDIO_MODEL`) — `SUMMARIZE_MODEL` wins if both are set. Example for a local Ollama setup:

```
SUMMARIZE_BACKEND=ollama
OLLAMA_MODEL=hermes-qwen35b:latest
```

**Note:** pressing `B` to cycle backends at runtime only auto-fills a model name for `openrouter` and `ollama` (which have sane defaults). Cycling to `llamacpp`, `lmstudio`, or `local` clears the model field — the status bar shows `(?)` until you set one via `SUMMARIZE_MODEL`/`.env` and restart, since there's no single "right" model name for a generic local server.

## Editing .env From the TUI

Press `D` at any time to open `.env` in `$EDITOR`. If no `.env` exists yet (first run), one is created by copying `.env.example` so you always have something concrete to edit — including a first-time `OPENROUTER_API_KEY=` line to fill in.

The TUI suspends while the editor is open (same mechanism as `E` for prompts) and reloads configuration the moment you save and quit — no restart needed. The meta row and status bar reflect the new backend/model immediately.

This is the fastest way to switch backends permanently (as opposed to `B`'s temporary in-session cycling): press `D`, change `SUMMARIZE_BACKEND` and the relevant `*_MODEL` line, save, and the new backend is active for the rest of the session and every future launch.

## Prompt Presets

Prompts live in `~/.config/transcriber/prompts.yaml` (created automatically on first run from the shipped `prompts.yaml`). Edit them in vim by pressing `E` in the TUI, or edit the file directly and press `R` to reload.

Built-in presets: `meeting_summary`, `lecture_notes`, `quick_recap`, and `custom` (the "edit-over-time" prompt).

## Configuration

All settings via environment or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUMMARIZE_BACKEND` | `openrouter` | Backend: `openrouter`, `ollama`, `llamacpp`, `lmstudio`, or `local` |
| `SUMMARIZE_MODEL` | *(backend-dependent)* | Model name for the active summarization backend |
| `SUMMARIZE_BASE_URL` | *(backend-dependent)* | Override the default base URL for any backend |
| `OPENROUTER_API_KEY` | *(required for openrouter)* | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `deepseek/deepseek-v4-flash-0731` | Cloud LLM model (openrouter backend) |
| `OLLAMA_MODEL` | `hermes-qwen35b:latest` | Local model name (ollama backend) |
| `LLAMACPP_MODEL` | *(empty)* | Local model name (llamacpp backend) |
| `LMSTUDIO_MODEL` | *(empty)* | Local model name (lmstudio backend) |
| `WHISPER_MODEL` | `base` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `EDITOR` | `vim` | Text editor for prompt (`E`) and `.env` (`D`) editing |

## Architecture

```
transcriber/
├── app.py          # Textual TUI (layout, bindings, worker flows)
├── config.py       # .env loading, backends, Config dataclass
├── picker.py       # Modal file picker with filtered DirectoryTree
├── prompts.py      # PromptStore — YAML load/save/reload
├── transcribe.py   # faster-whisper wrapper (thread-safe model cache)
├── summarize.py    # multi-backend streaming summarization (OpenRouter/Ollama/llama.cpp/LM Studio)
├── __main__.py     # `python -m transcriber` entry point
└── __init__.py
```

Transcription runs in a worker thread (CPU-bound), summarization runs as an async generator that streams tokens into the TUI live.

## License

MIT