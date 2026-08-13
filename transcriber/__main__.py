"""Package entry point: `python -m transcriber [audio_file]`."""
import sys

from .app import run


def main() -> None:
    # Accept an optional audio file path as the first CLI argument.
    audio_path = sys.argv[1] if len(sys.argv) > 1 else None
    run(audio_path)


if __name__ == "__main__":
    main()