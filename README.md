# transcriber-tui

A Textual TUI that transcribes audio files with local [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and summarizes the transcript with an LLM — via [OpenRouter](https://openrouter.ai) in the cloud, or a local model through Ollama, llama.cpp, LM Studio, or any OpenAI-compatible server.

**Zero transcription cost** — Whisper runs locally on CPU. Summarization uses your OpenRouter key or a local model (Ollama / llama.cpp / LM Studio).

## Features

- Transcribe any audio file with local Whisper (225x realtime on CPU with the `base` model)
- Built-in file browser — launch with no args and navigate freely up and down the filesystem in the TUI (not restricted to any starting directory)
- Summarize with **OpenRouter** (cloud) or **local models** via Ollama / llama.cpp / LM Studio / any OpenAI-compatible endpoint
- Stream summaries from an LLM with live token display
- Cycle backends at runtime with `B` — switch between cloud and local models without restarting
- Editable summarization prompts — press `E` to open in your editor, save, and reload
- Edit `.env` (API key, backend, model) directly from the TUI with `D` — no manual file hunting
- Export the transcript + summary to a standalone markdown file with `X` — open it in any editor, viewer, or note app outside the TUI
- One-key full workflow: `F` transcribes, summarizes, and exports in a single action — the common case of "here's a file, give me a summary I can read elsewhere"
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

**Fast path:** browse to (or pass) an audio file, then press `F` — transcribe, summarize, and export to markdown all happen in one action.

## Keyboard Reference

| Key | Action |
|-----|--------|
| `F` | **Full workflow:** transcribe → summarize → export, in one action |
| `T` | Transcribe the selected audio file |
| `O` | Browse for an audio file (file picker) |
| `S` | Summarize the transcript |
| `B` | Cycle summarization backend (openrouter → ollama → llamacpp → lmstudio → local) |
| `E` | Edit prompts in `$EDITOR` (auto-detected: nano/vi/vim/emacs) |
| `D` | Edit `.env` in `$EDITOR` — creates it from `.env.example` if missing |
| `X` | Export transcript + summary to a `.md` file (also a button next to Transcribe) |
| `R` | Reload prompts from disk |
| `C` | Cycle to the next prompt preset |
| `Q` | Quit |

## Browsing for a File

Press `O` (or click Browse) to open the file picker. It starts at your home directory but is not restricted to it — you can navigate anywhere on the filesystem the process can read:

| Key | Action |
|-----|--------|
| `Enter` / click | Open a folder, or select a file |
| `Backspace` / `U` / `-` | Go up one directory (re-roots the tree at the parent) |
| `H` | Jump straight to your home directory |
| `G` | Jump straight to the filesystem root (`/`) |
| `↑` `↓` | Move the cursor within the current directory listing |
| `Esc` | Cancel and close the picker |

The current directory is shown at the top of the picker so you always know where you are. Only directories and recognized audio/video files are listed — everything else is filtered out.

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

## Full Workflow (One Key)

The common case: you have an audio file, and you just want a summary you can read somewhere other than this terminal. Point the file input at it (type a path, `O` to browse, or pass it on the command line) and press `F` — or click the "Full Workflow" button.

`F` runs transcribe → summarize → export as a single chained action:

1. Transcribes the audio (status shows `[1/3] Transcribing ...`)
2. Feeds the transcript to the active summarization backend and prompt preset (`[2/3] ... summarizing ...`)
3. Writes both to a markdown file (`[3/3] Exporting markdown ...`)
4. Final status: `Done — transcribed, summarized, and exported to <path>`

If any stage fails, the chain stops there rather than continuing with bad or missing data — a failed transcription never gets "summarized" from an empty transcript, and a failed summarization never gets exported. Whatever succeeded before the failure (e.g. a good transcript when only summarization failed) stays visible in its pane and can still be exported on its own with `X`.

`F` respects the same backend, prompt preset, and `EXPORT_DIR` settings as running each step manually — it's exactly equivalent to pressing `T`, waiting, `S`, waiting, `X`, just without the waiting-and-pressing-again.

## Exporting to Markdown

Everything you see in the Transcript and Summary panes stays inside the TUI unless you export it. Press `X` (or click "Export .md") to write both to a single, self-contained markdown file you can open anywhere — a text editor, a markdown viewer, Obsidian, GitHub, etc.

The exported file includes a metadata header (source audio path, generation timestamp, prompt preset, and backend/model used) followed by the summary and the full timestamped transcript. You can export with just a transcript, just a summary, or both — whichever you've generated so far; `X` only refuses if there's genuinely nothing yet.

By default the file is saved next to the source audio, named `<audio-name>-summary-<timestamp>.md` (the timestamp keeps repeated exports from overwriting each other). Set `EXPORT_DIR` in `.env` to send exports somewhere else instead — e.g. a dedicated notes folder. The directory is created automatically if it doesn't exist yet, so pointing `EXPORT_DIR` at a brand-new notes vault works on the very first export:

```
EXPORT_DIR=~/notes/meeting-summaries
```

## Prompt Presets

Prompts live in **`~/.config/transcriber/prompts.yaml`** — this is the only file the running app ever reads from or writes to. There is a second `prompts.yaml` at the root of this repo, but that one is just the shipped *template*: it gets copied to the live location once, the very first time the app runs on a machine with no live file yet, and is never read again after that. Editing the repo copy directly has no effect once the live file exists — always use `E` in the TUI (or edit `~/.config/transcriber/prompts.yaml` directly, then `R` to reload) to change what the app actually uses.

Edit prompts in your editor by pressing `E` in the TUI (this now correctly reloads the file from disk when the editor closes), or edit `~/.config/transcriber/prompts.yaml` directly and press `R` to reload.

Built-in presets: `meeting_summary`, `lecture_notes`, `quick_recap`, and `custom` (the "edit-over-time" prompt).

**`meeting_summary` is active by default** on a fresh install — the TUI does not simply pick presets alphabetically (which would default to `custom`, a placeholder with no real instructions). Press `C` to cycle to a different preset; whichever one you land on is remembered in `~/.config/transcriber/last_prompt.txt` and stays active across restarts until you cycle again.

**Quoting in prompt text:** `prompts.yaml` values are YAML double-quoted strings. If your prompt text itself contains a `"` character (common in natural-language instructions, e.g. mentioning `"said"` vs `"sad"`), you must escape it as `\"` or the file becomes invalid YAML. The app catches this and shows a clear error in the status bar instead of crashing, but the safest fix is to write the prompt without straight quotes (use `'single quotes'` or no quotes at all in the prose) or switch that one value to YAML's block-literal style (`|` or `>`) which doesn't need escaping.

## Configuration

All settings via environment or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SUMMARIZE_BACKEND` | `openrouter` | Backend: `openrouter`, `ollama`, `llamacpp`, `lmstudio`, or `local` |
| `SUMMARIZE_MODEL` | *(backend-dependent)* | Model name for the active summarization backend |
| `SUMMARIZE_BASE_URL` | *(backend-dependent)* | Override the default base URL for any backend |
| `OPENROUTER_API_KEY` | *(required for openrouter)* | Your OpenRouter API key — must start with `sk-or-`. A key from another provider (e.g. OpenAI's `sk-proj-...`) is rejected at startup with a clear error instead of a confusing 401 from OpenRouter. |
| `OPENROUTER_MODEL` | `deepseek/deepseek-v4-flash-0731` | Cloud LLM model (openrouter backend) |
| `OLLAMA_MODEL` | `hermes-qwen35b:latest` | Local model name (ollama backend) |
| `LLAMACPP_MODEL` | *(empty)* | Local model name (llamacpp backend) |
| `LMSTUDIO_MODEL` | *(empty)* | Local model name (lmstudio backend) |
| `WHISPER_MODEL` | `base` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `EXPORT_DIR` | *(next to source audio)* | Directory for `X`/`F` markdown exports. Supports `~`; created automatically if it doesn't exist. |
| `EDITOR` | *(auto-detected)* | Text editor for prompt (`E`) and `.env` (`D`) editing. If unset, or if it points at something not installed, falls back through `nano` → `vi` → `vim` → `emacs`, whichever is actually on PATH. |

## Architecture

```
transcriber/
├── app.py          # Textual TUI (layout, bindings, worker flows)
├── config.py       # .env loading, backends, Config dataclass
├── export.py       # Markdown export (X): build/save transcript+summary docs
├── picker.py       # Modal file picker: filtered DirectoryTree + free up/down/home/root navigation
├── prompts.py      # PromptStore — YAML load/save/reload
├── transcribe.py   # faster-whisper wrapper (thread-safe model cache)
├── summarize.py    # multi-backend streaming summarization (OpenRouter/Ollama/llama.cpp/LM Studio)
├── __main__.py     # `python -m transcriber` entry point
└── __init__.py
```

Transcription runs in a worker thread (CPU-bound), summarization runs as an async generator that streams tokens into the TUI live.

## Troubleshooting

**`Summarization failed: HTTP 401: "Missing Authentication header"`** — `OPENROUTER_API_KEY` in `.env` is not a valid OpenRouter key. The most common cause is pasting a key from a different provider by mistake (OpenAI keys start with `sk-proj-`, Anthropic with `sk-ant-`; OpenRouter keys start with `sk-or-`). The app checks this at startup and shows a specific error for known cases, but if you edited `.env` mid-session, press `D` to fix it — the config reloads immediately, no restart needed. Get a real key at https://openrouter.ai/keys.

**`FileNotFoundError` on `E` or `D`** — fixed in current versions; `$EDITOR` is auto-detected with a fallback chain (`nano`/`vi`/`vim`/`emacs`) rather than assuming `vim` is installed. Pull the latest if you still see this.

**"I edited prompts.yaml but the TUI still uses the old text"** — you likely edited the repo's `prompts.yaml` (the shipped template) instead of `~/.config/transcriber/prompts.yaml` (the live file the app actually reads). See [Prompt Presets](#prompt-presets) above. Copy your edits into the live file, or better, use `E` in the TUI going forward so this can't happen.

**`prompts.yaml has invalid YAML and could not be reloaded`** — a `"` character inside your prompt text broke the YAML double-quoted string it lives in. See the quoting note under [Prompt Presets](#prompt-presets). The app keeps using the last successfully-loaded prompts rather than crashing, so fix the file and press `R` (or `E` again) once it's valid.

## License

MIT