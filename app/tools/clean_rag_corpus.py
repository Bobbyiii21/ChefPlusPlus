#!/usr/bin/env python3
"""
Delete every document from the Vertex AI RAG corpus configured by
``VERTEX_RAG_CORPUS``.

Run from the ``app/`` directory (same as ``manage.py``)::

    python -m tools.clean_rag_corpus --dry-run
    python -m tools.clean_rag_corpus --yes

Requires Google Application Default Credentials and env vars documented in
``tools.rag_files`` (``GOOGLE_CLOUD_PROJECT``, ``VERTEX_AI_LOCATION``,
``VERTEX_RAG_CORPUS``).

Optional: ``--reset-django-rag-pointers`` clears ``rag_resource_name`` on all
``developer.DatabaseFile`` rows so the app DB matches an empty corpus (does
not delete GCS blobs or local ``DatabaseFile`` rows).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap() -> None:
    app_dir = Path(__file__).resolve().parent.parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    from tools.env_config import _ensure_dotenv

    _ensure_dotenv()


def _reset_django_rag_pointers() -> int:
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chefplusplus.settings")
    import django

    django.setup()
    from developer.models import DatabaseFile

    return DatabaseFile.objects.exclude(rag_resource_name="").update(
        rag_resource_name=""
    )


def main() -> int:
    _bootstrap()

    parser = argparse.ArgumentParser(
        description="Remove all files from the Vertex RAG corpus."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List corpus files only; do not delete.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt (destructive).",
    )
    parser.add_argument(
        "--reset-django-rag-pointers",
        action="store_true",
        help="After deletes, blank rag_resource_name on all DatabaseFile rows.",
    )
    args = parser.parse_args()

    from tools.rag_files import clear_corpus, list_files

    try:
        pending = list_files()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not pending:
        print("Corpus is already empty (0 files).")
        return 0

    action = "Would delete" if args.dry_run else "About to delete"
    print(f"{action} {len(pending)} file(s):")
    for f in pending:
        label = f.display_name or "(no display name)"
        print(f"  - {label}")
        print(f"    {f.name}")

    if args.dry_run:
        print("\nDry run: no changes made.")
        return 0

    if not args.yes:
        try:
            confirm = input("\nType YES to delete all of the above: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 130
        if confirm != "YES":
            print("Aborted.")
            return 1

    try:
        deleted = clear_corpus(dry_run=False)
    except Exception as exc:
        print(f"Delete failed: {exc}", file=sys.stderr)
        return 1

    print(f"\nDeleted {len(deleted)} file(s) from the corpus.")

    if args.reset_django_rag_pointers:
        try:
            n = _reset_django_rag_pointers()
        except Exception as exc:
            print(
                f"Warning: could not reset Django rag_resource_name: {exc}",
                file=sys.stderr,
            )
            return 0
        print(f"Blanked rag_resource_name on {n} DatabaseFile row(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
