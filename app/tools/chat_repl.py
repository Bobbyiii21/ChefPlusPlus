#!/usr/bin/env python3
"""
Tiny REPL for testing vertex_chat from the terminal.

Run from the ``app/`` directory::

    python -m tools.chat_repl

Commands:
    /prompt         — print the current system prompt
    /setprompt      — enter a new system prompt (multi-line, end with a blank line)
    /resetprompt    — restore the default system prompt
    /clear          — clear conversation history
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


def main() -> int:
    _bootstrap()

    try:
        import readline  # noqa: F401 — enables arrow-key line editing
    except ImportError:
        pass

    from tools.vertex_chat import (
        get_system_prompt,
        reset_system_prompt,
        run_chat,
        set_system_prompt,
    )

    history: list[dict[str, str]] = []

    print("vertex_chat REPL  —  /quit to exit, /prompt /setprompt /resetprompt /clear\n")

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not line:
            continue

        if line in ("/quit", "/exit", "/q"):
            print("Bye.")
            return 0

        if line == "/clear":
            history.clear()
            print("(history cleared)\n")
            continue

        if line == "/prompt":
            print(f"\n--- system prompt ---\n{get_system_prompt()}\n--- end ---\n")
            continue

        if line == "/setprompt":
            print("Enter new prompt (blank line to finish):")
            lines: list[str] = []
            while True:
                try:
                    part = input("...  ")
                except (EOFError, KeyboardInterrupt):
                    break
                if part == "":
                    break
                lines.append(part)
            if lines:
                set_system_prompt("\n".join(lines))
                print("(system prompt updated)\n")
            else:
                print("(cancelled)\n")
            continue

        if line == "/resetprompt":
            reset_system_prompt()
            print("(system prompt reset to default)\n")
            continue

        if line.startswith("/"):
            print(f"Unknown command: {line}\n")
            continue

        result = run_chat(line, history or None)
        err = result.get("error", "")
        reply = result.get("reply", "")

        if err:
            print(f"error> {err}\n")
        else:
            print(f"bot> {reply}\n")
            history.append({"role": "user", "content": line})
            history.append({"role": "model", "content": reply})


if __name__ == "__main__":
    raise SystemExit(main())
