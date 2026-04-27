"""
Generate a short catalog description for a RAG source using Vertex Gemini.

Uses the same default model as :mod:`tools.text_cleaner` (``VERTEX_TEXT_CLEANER_MODEL``).
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import vertexai
from google.api_core import exceptions as google_exceptions
from google.auth import exceptions as google_auth_exceptions
from vertexai.generative_models import Content, GenerativeModel, Part

from tools.env_config import (
    google_cloud_project,
    vertex_ai_location,
    vertex_text_cleaner_model,
)

logger = logging.getLogger(__name__)

_MAX_DESCRIPTION_LEN = 1023
_MAX_INPUT_CHARS = 100_000

_SYSTEM_PROMPT = """
You write brief descriptions for documents in a nutrition / dietary-health knowledge base.

Given the document text (which may be truncated), write ONE short paragraph (2–4 sentences)
that summarizes what the document is about and what a reader would learn from it.
The excerpt may be plain text or pretty-printed JSON representing structured data.

Rules:
- Plain text only. No markdown, bullets, or title line.
- Do not invent facts; only use what is supported by the excerpt.
- Be concise. The description must not exceed 900 characters.
""".strip()

_lock = threading.Lock()
_cached_model: Optional[GenerativeModel] = None
_vertex_inited = False


def _init_vertex() -> None:
    global _vertex_inited
    if _vertex_inited:
        return
    project = google_cloud_project()
    location = vertex_ai_location()
    vertexai.init(project=project, location=location)
    logger.info("vertexai.init project=%s location=%s", project, location)
    _vertex_inited = True


def _build_model() -> GenerativeModel:
    _init_vertex()
    model_id = vertex_text_cleaner_model()
    logger.info("Description-summary model: %s", model_id)
    return GenerativeModel(
        model_name=model_id,
        system_instruction=_SYSTEM_PROMPT,
    )


def _get_model() -> GenerativeModel:
    global _cached_model
    with _lock:
        if _cached_model is None:
            _cached_model = _build_model()
        return _cached_model


def summarize_for_description(body_text: str) -> dict[str, str]:
    """
    Return ``{"description": str, "error": str}`` — on failure *description* is empty.
    """
    text = (body_text or "").strip()
    if not text:
        return {"description": "", "error": "No text to summarize."}

    if len(text) > _MAX_INPUT_CHARS:
        text = text[:_MAX_INPUT_CHARS]

    user_prompt = (
        "Summarize the following document for the knowledge-base description field.\n\n"
        "---\n"
        f"{text}\n"
        "---"
    )

    try:
        model = _get_model()
        contents = [Content(role="user", parts=[Part.from_text(user_prompt)])]
        response = model.generate_content(contents)
    except (ValueError, RuntimeError) as exc:
        logger.exception("Configuration error")
        return {"description": "", "error": str(exc)}
    except google_auth_exceptions.DefaultCredentialsError:
        logger.warning("Application Default Credentials not found")
        return {
            "description": "",
            "error": (
                "Google Application Default Credentials are not set. "
                "Run: gcloud auth application-default login"
            ),
        }
    except google_exceptions.GoogleAPIError as exc:
        logger.exception("Vertex AI API error")
        detail = getattr(exc, "message", None) or str(exc)
        return {"description": "", "error": f"AI service error: {detail}"}

    if not response.candidates:
        return {
            "description": "",
            "error": "No response from the model (blocked or empty).",
        }

    try:
        reply_text = response.text or ""
    except ValueError:
        return {
            "description": "",
            "error": "The model returned no text (safety filter or empty parts).",
        }

    out = reply_text.strip()
    if len(out) > _MAX_DESCRIPTION_LEN:
        out = out[:_MAX_DESCRIPTION_LEN].rstrip()
    return {"description": out, "error": ""}
