"""
Centralised environment-variable access for the ChefPlusPlus project.

Resolution order for every variable:
  1. ``os.environ`` (set by the shell, Docker, Cloud Run, etc.)
  2. ``.env`` files loaded via *python-dotenv* (repo-root then app-local)

Import the helpers you need from this module instead of calling
``os.environ`` / ``os.getenv`` directly — this keeps the dotenv
bootstrap in one place and gives clear errors when a required
variable is missing.

Usage::

    from tools.env_config import get_env, require_env

    project = require_env("GOOGLE_CLOUD_PROJECT")   # raises on missing
    region  = get_env("VERTEX_AI_LOCATION", "us-central1")  # default OK
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_dotenv_loaded = False


def _ensure_dotenv() -> None:
    """Load ``.env`` files once, silently skip if python-dotenv is absent."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    app_dir = Path(__file__).resolve().parent.parent  # …/app
    repo_root = app_dir.parent

    root_env = repo_root / ".env"
    app_env = app_dir / ".env"

    if root_env.exists():
        load_dotenv(root_env)
    if app_env.exists():
        load_dotenv(app_env, override=True)


class EnvVarMissing(RuntimeError):
    """A required environment variable is not set."""


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return an env var, falling back to dotenv files then *default*."""
    _ensure_dotenv()
    value = os.environ.get(name)
    if value is not None:
        value = value.strip()
        return value if value else default
    return default


def require_env(name: str) -> str:
    """Return an env var or raise :class:`EnvVarMissing`."""
    value = get_env(name)
    if not value:
        raise EnvVarMissing(
            f"Required environment variable '{name}' is not set. "
            f"Export it in your shell, add it to .env, or set it in your "
            f"deployment configuration."
        )
    return value


# ── Convenience accessors for the known project variables ──────────

def google_cloud_project() -> str:
    """``GOOGLE_CLOUD_PROJECT`` — required."""
    return require_env("GOOGLE_CLOUD_PROJECT")


def vertex_ai_location() -> str:
    """``VERTEX_AI_LOCATION`` — defaults to ``us-central1``."""
    return get_env("VERTEX_AI_LOCATION", "us-central1")


def vertex_chat_model() -> str:
    """``VERTEX_CHAT_MODEL`` — required."""
    return require_env("VERTEX_CHAT_MODEL")


def vertex_rag_corpus() -> Optional[str]:
    """``VERTEX_RAG_CORPUS`` — optional, ``None`` when unset."""
    return get_env("VERTEX_RAG_CORPUS")


def vertex_text_cleaner_model() -> str:
    """``VERTEX_TEXT_CLEANER_MODEL`` — defaults to ``gemini-2.0-flash-lite``."""
    return get_env("VERTEX_TEXT_CLEANER_MODEL", "gemini-2.0-flash-lite")


def gcs_bucket() -> str:
    """``GCS_BUCKET`` — required for Cloud Storage uploads."""
    return require_env("GCS_BUCKET")
