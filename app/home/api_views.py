from __future__ import annotations

import json
import logging
from typing import Any

from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _normalize_history(raw_history: Any) -> list[dict[str, str]] | None:
    if raw_history is None:
        return None
    if not isinstance(raw_history, list):
        raise ValueError("history must be a list")

    normalized: list[dict[str, str]] = []
    for turn in raw_history:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "").strip().lower()
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        normalized.append(
            {
                "role": "user" if role == "user" else "assistant",
                "content": content,
            }
        )
    return normalized


def _run_chat(message: str, history: list[dict[str, str]] | None) -> dict[str, str]:
    try:
        from .vertex_chat import run_dietary_assistant_chat
    except ImportError:
        logger.exception("Vertex AI dependencies are unavailable")
        return {
            "reply": "",
            "error": (
                "Vertex AI dependencies are unavailable. "
                "Install google-cloud-aiplatform in this environment."
            ),
        }
    return run_dietary_assistant_chat(message=message, history=history)


@require_POST
def chat_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"reply": "", "error": "Invalid JSON body."}, status=400)

    message = str(payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"reply": "", "error": "Message is required."}, status=400)

    try:
        history = _normalize_history(payload.get("history"))
    except ValueError:
        return JsonResponse(
            {"reply": "", "error": "history must be a list of chat turns."},
            status=400,
        )

    result = _run_chat(message=message, history=history)
    reply = str(result.get("reply") or "")
    error = str(result.get("error") or "")
    status_code = 200 if not error else 502
    return JsonResponse({"reply": reply, "error": error}, status=status_code)
