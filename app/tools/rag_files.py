"""
Manage files in a Vertex AI RAG corpus (vector store).

Provides simple helpers that front-end developers can call to **list**,
**import** (add), and **delete** files without touching the Vertex SDK
directly.

All environment access goes through :mod:`tools.env_config`.

Required env vars: GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION, VERTEX_RAG_CORPUS
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import vertexai
from vertexai import rag

from tools.env_config import (
    google_cloud_project,
    vertex_ai_location,
    vertex_rag_corpus,
)

logger = logging.getLogger(__name__)

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


def _corpus_name() -> str:
    """Return the full RAG corpus resource name or raise."""
    corpus = vertex_rag_corpus()
    if not corpus:
        raise RuntimeError(
            "VERTEX_RAG_CORPUS is not set. Cannot manage RAG files "
            "without a corpus resource name."
        )
    return corpus


# ── Data classes for structured results ──────────────────────────

@dataclass
class RagFileInfo:
    """Lightweight representation of a file in the RAG corpus."""
    display_name: str
    name: str


@dataclass
class ImportResult:
    """Result returned after importing files into the corpus."""
    imported_count: int
    raw_response: Any = field(repr=False, default=None)


# ── Public API ────────────────────────────────────────────────────

def list_files() -> list[RagFileInfo]:
    """
    List every file currently in the RAG corpus.

    Returns a list of :class:`RagFileInfo` with ``display_name`` and
    ``name`` (full resource path).
    """
    _init_vertex()
    corpus = _corpus_name()

    results: list[RagFileInfo] = []
    for f in rag.list_files(corpus_name=corpus):
        results.append(
            RagFileInfo(
                display_name=getattr(f, "display_name", ""),
                name=getattr(f, "name", ""),
            )
        )
    return results


def import_files(
    paths: Sequence[str],
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 100,
    import_result_sink: Optional[str] = None,
    max_embedding_requests_per_min: int = 900,
) -> ImportResult:
    """
    Import files into the RAG corpus from GCS or Google Drive URIs.

    Parameters
    ----------
    paths:
        List of ``gs://…`` or Google Drive URLs to import.
    chunk_size:
        Token chunk size for the transformation config (default 512).
    chunk_overlap:
        Overlap between chunks (default 100).
    import_result_sink:
        Optional ``gs://`` path to an *existing* bucket folder + unique
        filename where import results will be written as NDJSON.
    max_embedding_requests_per_min:
        Rate-limit for embedding requests (default 900).
    """
    if not paths:
        raise ValueError("At least one path is required for import.")

    _init_vertex()
    corpus = _corpus_name()

    kwargs: dict[str, Any] = {
        "corpus_name": corpus,
        "paths": list(paths),
        "transformation_config": rag.TransformationConfig(
            rag.ChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        ),
        "max_embedding_requests_per_min": max_embedding_requests_per_min,
    }
    if import_result_sink:
        kwargs["import_result_sink"] = import_result_sink

    response = rag.import_files(**kwargs)
    count = getattr(response, "imported_rag_files_count", 0)
    logger.info("Imported %s file(s) into corpus %s", count, corpus)
    return ImportResult(imported_count=count, raw_response=response)


def delete_file(file_name: str) -> None:
    """
    Delete a single file from the RAG corpus.

    Parameters
    ----------
    file_name:
        Full resource name, e.g.
        ``projects/{project}/locations/{loc}/ragCorpora/{id}/ragFiles/{id}``
    """
    if not file_name or not file_name.strip():
        raise ValueError("file_name is required.")

    _init_vertex()
    rag.delete_file(name=file_name.strip())
    logger.info("Deleted RAG file %s", file_name)
