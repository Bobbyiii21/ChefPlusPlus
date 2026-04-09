"""
Clean and prepare plain text for ingestion into a RAG vector store.

Sends raw text through a Vertex AI Gemini model with a system prompt
that instructs the model to:

- Prioritise the first / primary topic in the text.
- Strip extraneous data, boilerplate, and excess whitespace.
- Return a single cleaned string ready for chunking and embedding.

The model used defaults to ``gemini-2.0-flash-lite`` — a cheap,
large-context model suitable for high-token-count documents.  Override
with the ``VERTEX_TEXT_CLEANER_MODEL`` environment variable.

Usage::

    from tools.text_cleaner import clean_text

    cleaned = clean_text(raw_text)
    if cleaned["error"]:
        print("Something went wrong:", cleaned["error"])
    else:
        ready = cleaned["text"]

Environment variables (via ``tools.env_config``):
  GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION,
  VERTEX_TEXT_CLEANER_MODEL (optional, default ``gemini-2.0-flash-lite``).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

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

_SYSTEM_PROMPT = """
You are a text-cleaning pre-processor for a Retrieval-Augmented Generation
(RAG) pipeline.  Your ONLY job is to take the raw text the user provides and
return a cleaned version that is ready for chunking and embedding.

Rules you MUST follow:
1. Identify the PRIMARY topic of the text.  Keep all content that is
   directly relevant to that topic.
2. Remove all content that is not relevant to the primary topic, including
   navigation menus, headers/footers, ads, legal boilerplate, cookie
   notices, sidebars, and unrelated links.
3. Collapse all redundant whitespace (multiple spaces, blank lines, tabs)
   into single spaces or single newlines where a paragraph break is
   appropriate.
4. Preserve factual accuracy — do NOT add, infer, or fabricate information.
5. Preserve meaningful structure: keep paragraph breaks and ordered/
   unordered lists if they help comprehension, but remove purely
   decorative formatting (e.g. ASCII art, excessive dashes).
6. Do NOT wrap your output in markdown code fences, quotes, or any other
   container.  Return ONLY the cleaned plain text.
7. Do NOT include any commentary, explanation, or preamble.  The entire
   response must be the cleaned text and nothing else.
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
    logger.info("Text-cleaner model: %s", model_id)
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


def clean_text(raw_text: str) -> dict[str, str]:
    """
    Clean *raw_text* for RAG ingestion.

    Parameters
    ----------
    raw_text:
        The unprocessed plain text to clean.

    Returns
    -------
    dict
        ``{"text": str, "error": str}``  — on success *error* is ``""``;
        on failure *text* is ``""`` and *error* describes the problem.
    """
    text = (raw_text or "").strip()
    if not text:
        return {"text": "", "error": "Input text is required."}

    try:
        model = _get_model()
        contents = [Content(role="user", parts=[Part.from_text(text)])]
        response = model.generate_content(contents)
    except (ValueError, RuntimeError) as exc:
        logger.exception("Configuration error")
        return {"text": "", "error": str(exc)}
    except google_auth_exceptions.DefaultCredentialsError:
        logger.warning("Application Default Credentials not found")
        return {
            "text": "",
            "error": (
                "Google Application Default Credentials are not set. "
                "Run: gcloud auth application-default login"
            ),
        }
    except google_exceptions.GoogleAPIError as exc:
        logger.exception("Vertex AI API error")
        detail = getattr(exc, "message", None) or str(exc)
        return {"text": "", "error": f"AI service error: {detail}"}

    if not response.candidates:
        return {
            "text": "",
            "error": "No response from the model (blocked or empty).",
        }

    try:
        reply_text = response.text or ""
    except ValueError:
        return {
            "text": "",
            "error": "The model returned no text (safety filter or empty parts).",
        }

    return {"text": reply_text.strip(), "error": ""}
