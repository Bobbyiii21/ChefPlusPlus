"""
Clean and prepare plain text for ingestion into a RAG corpus.

Sends raw text through a Vertex AI generative model with a system prompt
that strips extraneous whitespace, removes tangential or duplicate
content, and foregrounds the **primary topic** so the resulting text is
compact, on-topic, and ready for embedding / chunking.

The cleaning model defaults to ``gemini-2.0-flash`` — a low-cost model
with a 1 M-token context window — and can be overridden with the
``VERTEX_TEXT_CLEANING_MODEL`` environment variable.

Usage::

    from tools.text_cleaner import clean_text

    cleaned = clean_text(raw_text)

Environment variables (via ``tools.env_config``):
  GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION,
  VERTEX_TEXT_CLEANING_MODEL (optional, default ``gemini-2.0-flash``).
"""

from __future__ import annotations

import logging
from typing import Optional

import vertexai
from vertexai.generative_models import GenerativeModel, Part

from tools.env_config import (
    get_env,
    google_cloud_project,
    vertex_ai_location,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a text-cleaning pre-processor for a Retrieval-Augmented Generation \
(RAG) pipeline.  Your ONLY job is to return a cleaned version of the user's \
text.  Follow these rules strictly:

1. **Identify the primary topic** of the text.  Keep all content that is \
   directly relevant to that topic.
2. **Remove** duplicate sentences, filler phrases, boilerplate disclaimers, \
   navigation chrome, headers/footers unrelated to the main content, \
   advertisements, and any tangential or off-topic material.
3. **Collapse** excessive whitespace, blank lines, and irregular formatting \
   into clean, single-spaced prose paragraphs.
4. **Preserve** factual data, proper nouns, numbers, dates, and any \
   technical terminology that is on-topic.
5. **Do not** add commentary, summaries, introductions, or metadata.  \
   Do not wrap the output in markdown fences or add headings that were \
   not in the original.
6. **Do not** rephrase or paraphrase the content.  Keep the original \
   wording wherever possible; only remove what is extraneous.
7. Return ONLY the cleaned text — nothing else.\
"""

_vertex_inited = False
_model: Optional[GenerativeModel] = None


def _cleaning_model_id() -> str:
    return get_env("VERTEX_TEXT_CLEANING_MODEL", "gemini-2.0-flash")


def _init_vertex() -> None:
    global _vertex_inited
    if _vertex_inited:
        return
    project = google_cloud_project()
    location = vertex_ai_location()
    vertexai.init(project=project, location=location)
    logger.info("vertexai.init project=%s location=%s", project, location)
    _vertex_inited = True


def _get_model() -> GenerativeModel:
    global _model
    if _model is None:
        _init_vertex()
        model_id = _cleaning_model_id()
        _model = GenerativeModel(
            model_name=model_id,
            system_instruction=_SYSTEM_PROMPT,
        )
        logger.info("Text-cleaning model: %s", model_id)
    return _model


def clean_text(raw_text: str) -> str:
    """
    Clean *raw_text* for RAG ingestion and return the result.

    Raises
    ------
    ValueError
        If *raw_text* is empty / whitespace-only.
    RuntimeError
        If the model returns no usable text.
    google.auth.exceptions.DefaultCredentialsError
        If GCP credentials are not configured.
    google.api_core.exceptions.GoogleAPIError
        On upstream API failures.
    """
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("raw_text must be a non-empty string.")

    model = _get_model()
    response = model.generate_content([Part.from_text(text)])

    if not response.candidates:
        raise RuntimeError(
            "The model returned no candidates (content may have been blocked)."
        )

    try:
        result = response.text or ""
    except ValueError as exc:
        raise RuntimeError(
            "The model returned no text (safety filter or empty parts)."
        ) from exc

    cleaned = result.strip()
    if not cleaned:
        raise RuntimeError("The model returned an empty response.")

    return cleaned
