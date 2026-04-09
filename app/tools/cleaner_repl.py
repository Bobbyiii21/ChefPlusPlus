#!/usr/bin/env python3
"""
Tiny REPL for testing text_cleaner from the terminal.

Run from the ``app/`` directory::

    python -m tools.cleaner_repl

Paste or type raw text, then enter a blank line to submit it for
cleaning.  The cleaned result is printed back.

Commands:
    /file <path>    — read a file from disk and clean its contents
    /quit, /exit    — exit
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
    app_dir = Path(__file__).resolve().parent.parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    from tools.env_config import _ensure_dotenv
    _ensure_dotenv()


def _read_multiline() -> str:
    """Read lines until a blank line is entered; return joined text."""
    lines: list[str] = []
    while True:
        try:
            part = input("...  ")
        except (EOFError, KeyboardInterrupt):
            break
        if part == "":
            break
        lines.append(part)
    return "\n".join(lines)


def _clean_and_print(raw: str) -> None:
    from tools.text_cleaner import clean_text

    if not raw.strip():
        print("(empty input, skipped)\n")
        return

    print("(cleaning…)")
    result = clean_text(raw)
    err = result.get("error", "")
    text = result.get("text", "")

    if err:
        print(f"error> {err}\n")
    else:
        print(f"\n--- cleaned ---\n{text}\n--- end ---\n")


def main() -> int:
    _bootstrap()

    try:
        import readline  # noqa: F401 — enables arrow-key line editing
    except ImportError:
        pass

    print(
        "text_cleaner REPL  —  paste text then press Enter on a blank line\n"
        "Commands: /file <path>, /quit\n"
    )

    while True:
        try:
            line = input("clean> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not line:
            continue

        if line in ("/quit", "/exit", "/q"):
            print("Bye.")
            return 0

        if line.startswith("/file"):
            parts = line.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                print("Usage: /file <path>\n")
                continue
            fpath = Path(parts[1].strip()).expanduser()
            if not fpath.is_file():
                print(f"File not found: {fpath}\n")
                continue
            try:
                raw = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"Could not read file: {exc}\n")
                continue
            print(f"(read {len(raw)} chars from {fpath})")
            _clean_and_print(raw)
            continue

        if line.startswith("/"):
            print(f"Unknown command: {line}\n")
            continue

        print("Paste remaining text (blank line to submit):")
        rest = _read_multiline()
        raw = line + "\n" + rest if rest else line
        _clean_and_print(raw)


if __name__ == "__main__":
    raise SystemExit(main())
