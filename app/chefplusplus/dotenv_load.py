from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_dotenv(app_dir: Path) -> None:
    """Load repo-root and app-local dotenv files if they exist."""
    app_dir = app_dir.resolve()
    repo_root = app_dir.parent

    root_env = repo_root / ".env"
    app_env = app_dir / ".env"

    if root_env.exists():
        load_dotenv(root_env)
    if app_env.exists():
        load_dotenv(app_env, override=True)
