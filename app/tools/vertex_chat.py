"""
Vertex AI (Gemini) chat with optional RAG retrieval and a
**runtime-modifiable system prompt**.

All environment access goes through :mod:`tools.env_config` so that
``os.environ`` → dotenv fallback is handled in one place.

Public API
----------
- ``get_system_prompt()``           — read the current system prompt
- ``set_system_prompt(text)``       — replace it (rebuilds the model)
- ``reset_system_prompt()``         — restore the built-in default
- ``run_chat(message, history)``    — send a turn to Gemini

Environment variables (via ``tools.env_config``):
  GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION, VERTEX_CHAT_MODEL,
  VERTEX_RAG_CORPUS (optional), VERTEX_RAG_TOP_K (optional, default 8).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import vertexai
from google.api_core import exceptions as google_exceptions
from google.auth import exceptions as google_auth_exceptions
from vertexai import rag
from vertexai.generative_models import Content, GenerativeModel, Part, Tool

from tools.env_config import (
    get_env,
    google_cloud_project,
    vertex_ai_location,
    vertex_chat_model,
    vertex_rag_corpus,
)

logger = logging.getLogger(__name__)

# ── Default system prompt ──────────────────────────────────────────

_DEFAULT_SYSTEM_PROMPT = """
# System Prompt: Dietary Health Assistant

## Role and Purpose

You are a friendly, knowledgeable dietary health assistant. Your job is to help
users make strong, informed choices about their nutrition in pursuit of their
personal health goals. Speak in plain, warm, encouraging language.

You are **not** a doctor or registered dietitian. When a user has a specific
health condition, always encourage them to consult a qualified healthcare
provider.

## Tone and Style

- Be warm, patient, and encouraging — never judgmental about food choices.
- Use simple, everyday language.
- Avoid overwhelming users with too much information at once.

## Knowledge Sources

1. **Dietary Guidelines for Americans, 2020–2025** (USDA & HHS)
2. **USDA FoodData Central** — detailed nutritional profiles.

## What You Should NOT Do

- Diagnose, treat, or provide clinical guidance for specific medical conditions.
- Recommend supplements as a substitute for food without noting the user should
  consult a healthcare provider.
- Make claims that any food cures or prevents disease.
- Shame or judge any food culture, dietary choice, or eating habit.
""".strip()

# ── Prompt storage and model cache (thread-safe) ──────────────────

_lock = threading.Lock()
_system_prompt: str = _DEFAULT_SYSTEM_PROMPT
_cached_model: Optional[GenerativeModel] = None
_vertex_inited = False


# ── System-prompt management ──────────────────────────────────────

def get_system_prompt() -> str:
    """Return the current system prompt text."""
    with _lock:
        return _system_prompt


def set_system_prompt(prompt: str) -> None:
    """Replace the system prompt and invalidate the cached model."""
    if not prompt or not prompt.strip():
        raise ValueError("System prompt cannot be empty.")
    with _lock:
        global _system_prompt, _cached_model
        _system_prompt = prompt.strip()
        _cached_model = None


def reset_system_prompt() -> None:
    """Restore the built-in default system prompt."""
    set_system_prompt(_DEFAULT_SYSTEM_PROMPT)


# ── Vertex AI initialisation / model building ────────────────────

def _init_vertex() -> None:
    global _vertex_inited
    if _vertex_inited:
        return
    project = google_cloud_project()
    location = vertex_ai_location()
    vertexai.init(project=project, location=location)
    logger.info("vertexai.init project=%s location=%s", project, location)
    _vertex_inited = True


def _rag_top_k() -> int:
    raw = get_env("VERTEX_RAG_TOP_K", "8")
    try:
        top_k = int(raw)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 8
    return max(1, min(top_k, 32))


def _build_model(prompt: str) -> GenerativeModel:
    _init_vertex()
    model_id = vertex_chat_model()
    corpus = vertex_rag_corpus()
    top_k = _rag_top_k()

    kwargs: dict[str, Any] = {
        "model_name": model_id,
        "system_instruction": prompt,
    }

    if corpus:
        rag_cfg = rag.RagRetrievalConfig(top_k=top_k)
        rag_tool = Tool.from_retrieval(
            retrieval=rag.Retrieval(
                source=rag.VertexRagStore(
                    rag_resources=[rag.RagResource(rag_corpus=corpus)],
                    rag_retrieval_config=rag_cfg,
                ),
            )
        )
        kwargs["tools"] = [rag_tool]
        logger.info("GenerativeModel with RAG corpus top_k=%s", top_k)
    else:
        logger.warning(
            "VERTEX_RAG_CORPUS is unset; using Gemini without retrieval."
        )

    return GenerativeModel(**kwargs)


def _get_model() -> GenerativeModel:
    global _cached_model
    with _lock:
        if _cached_model is None:
            _cached_model = _build_model(_system_prompt)
        return _cached_model


# ── Chat execution ────────────────────────────────────────────────

def _build_contents(
    history: list[dict[str, Any]] | None,
    message: str,
) -> list[Content]:
    contents: list[Content] = []
    for turn in history or []:
        role = (turn.get("role") or "").strip().lower()
        text = (turn.get("content") or "").strip()
        if not text:
            continue
        model_role = "user" if role == "user" else "model"
        contents.append(Content(role=model_role, parts=[Part.from_text(text)]))
    contents.append(Content(role="user", parts=[Part.from_text(message)]))
    return contents


def run_chat(
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Send *message* (with optional multi-turn *history*) to Vertex Gemini.

    Returns ``{"reply": str, "error": str}``.
    """
    text = (message or "").strip()
    if not text:
        return {"reply": "", "error": "Message is required."}

    try:
        model = _get_model()
        contents = _build_contents(history, text)
        response = model.generate_content(contents)
    except (ValueError, RuntimeError) as exc:
        logger.exception("Configuration error")
        return {"reply": "", "error": str(exc)}
    except google_auth_exceptions.DefaultCredentialsError:
        logger.warning("Application Default Credentials not found")
        return {
            "reply": "",
            "error": (
                "Google Application Default Credentials are not set. "
                "Run: gcloud auth application-default login"
            ),
        }
    except google_exceptions.GoogleAPIError as exc:
        logger.exception("Vertex AI API error")
        detail = getattr(exc, "message", None) or str(exc)
        return {"reply": "", "error": f"AI service error: {detail}"}

    if not response.candidates:
        return {
            "reply": "",
            "error": "No response from the model (blocked or empty).",
        }

    try:
        reply_text = response.text or ""
    except ValueError:
        return {
            "reply": "",
            "error": "The model returned no text (safety filter or empty parts).",
        }

    return {"reply": reply_text.strip(), "error": ""}
