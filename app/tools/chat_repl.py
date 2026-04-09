#!/usr/bin/env python3
"""
Interactive terminal to exercise tools.ai (Vertex Gemini + optional RAG).

Run from the directory that contains `manage.py` (usually `app/`):

  cd app    # skip if your prompt already ends with .../app
  python -m tools.chat_repl

Requires: Application Default Credentials — run once on your machine:

  gcloud auth application-default login

Also set in `.env` next to the `app/` folder (repo root) or in `app/.env`, or export in the shell:
  GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION, VERTEX_CHAT_MODEL
  optional: VERTEX_RAG_CORPUS, VERTEX_RAG_TOP_K

Commands: /quit /exit, /clear (reset history), /help
"""

from __future__ import annotations

import argparse
import sys
import warnings


def _ensure_app_on_path() -> None:
    """Allow `python tools/chat_repl.py` from repo app/ folder."""
    from pathlib import Path

    app_dir = Path(__file__).resolve().parent.parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))


def _load_dotenv_files() -> None:
    from pathlib import Path

    app_dir = Path(__file__).resolve().parent.parent
    try:
        from chefplusplus.dotenv_load import load_project_dotenv
    except ImportError:
        return
    load_project_dotenv(app_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description='REPL for dietary assistant (tools.ai).')
    parser.add_argument(
        '--single',
        action='store_true',
        help='One-shot mode: exit after the first reply (no multi-turn history).',
    )
    args = parser.parse_args()

    warnings.filterwarnings(
        'ignore',
        message='.*end of life.*',
        category=FutureWarning,
    )
    warnings.filterwarnings(
        'ignore',
        message='.*deprecated as of June 24, 2025.*',
        category=UserWarning,
    )

    _ensure_app_on_path()
    _load_dotenv_files()

    try:
        import readline  # pylint: disable=unused-import  # enables line editing
    except ImportError:
        pass

    from tools.ai import run_dietary_assistant_chat

    history: list[dict[str, str]] = []

    print('Dietary assistant REPL (tools.ai). Type /help for commands.\n')

    while True:
        try:
            line = input('you> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nBye.')
            return 0

        if not line:
            continue

        if line in ('/quit', '/exit', '/q'):
            print('Bye.')
            return 0

        if line == '/clear':
            history.clear()
            print('(history cleared)\n')
            continue

        if line == '/help':
            print(
                '  /quit, /exit  — exit\n'
                '  /clear        — clear conversation history\n'
                '  /help         — this text\n'
                '  Other text    — sent to Vertex (not shell commands; typos like '
                '"ds" call the API)\n'
                '\n'
                '  Local auth: gcloud auth application-default login\n'
            )
            continue

        if line.startswith('/'):
            print(f'Unknown command: {line} (try /help)\n')
            continue

        result = run_dietary_assistant_chat(line, history or None)
        err = (result.get('error') or '').strip()
        reply = (result.get('reply') or '').strip()

        if err:
            print(f'error> {err}\n')
        else:
            print(f'bot> {reply}\n')

        if not err and reply:
            history.append({'role': 'user', 'content': line})
            history.append({'role': 'model', 'content': reply})

        if args.single:
            return 0 if not err else 1


if __name__ == '__main__':
    raise SystemExit(main())
