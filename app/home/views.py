import json
import re

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from developer.models import DatabaseFile


def _rag_documents_system_prompt_suffix() -> str:
    """Human-readable list of DB files (name + description) for the chat system prompt."""
    rows = list(
        DatabaseFile.objects.order_by("name").values_list("name", "description")
    )
    if not rows:
        return ""
    lines: list[str] = [
        "## Documents in the retrieval corpus (from your library)",
        "",
        "The RAG index may return passages from these items. Prefer citing them by "
        "the display name below (not internal file paths). Each line is "
        "``name``: summary from the uploader.",
        "",
    ]
    for name, description in rows:
        name = (name or "").strip() or "(untitled)"
        desc = " ".join((description or "").split())
        if not desc:
            desc = "(No description provided.)"
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


_SOURCE_LINE_RE = re.compile(
    r"(?im)^\s*source:\s*(?P<sources>.+?)\s*$",
)


def _source_line_chunks(reply: str) -> list[str]:
    """Split the first ``Source:`` line into comma/semicolon-separated parts."""
    text = (reply or "").strip()
    match = _SOURCE_LINE_RE.search(text)
    if not match:
        return []
    raw = (match.group("sources") or "").strip()
    if not raw:
        return []
    parts = re.split(r"[,;]", raw)
    return [p.strip() for p in parts if p.strip()]


def reference_downloads_for_reply(request, reply: str) -> list[dict[str, str]]:
    """
    Match ``Source:`` segments to uploaded :class:`~developer.models.DatabaseFile`
    rows (file-backed only) and return absolute download URLs.
    """
    chunks = _source_line_chunks(reply)
    if not chunks:
        return []

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        key = chunk.casefold()
        if key in seen:
            continue
        seen.add(key)
        dbf = DatabaseFile.objects.filter(name__iexact=chunk).first()
        if dbf is None:
            continue
        if not dbf.file:
            continue
        try:
            url = request.build_absolute_uri(dbf.file.url)
        except ValueError:
            continue
        out.append({"name": dbf.name, "url": url})
    return out


def index(request):
    template_data = {}
    template_data['title'] = 'Chef++'
    return render(request, 'home/index.html', {'template_data': template_data})

def about(request):
    return render(request, 'home/about.html')

def chat(request):
    template_data = {}
    template_data['title'] = 'Chat'
    return render(request, 'home/chat.html', {'template_data': template_data})


@csrf_exempt
@require_POST
def chat_api(request):
    """Accept a JSON body with ``message`` and optional ``history``,
    forward to Vertex AI via ``run_chat``, and return the reply."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"reply": "", "error": "Invalid JSON."}, status=400)

    message = (body.get("message") or "").strip()
    if not message:
        return JsonResponse({"reply": "", "error": "Message is required."}, status=400)

    history = body.get("history")

    from tools.prompt_router import build_chat_system_prompt_suffix, classify_intent
    from tools.vertex_chat import run_chat

    doc_index = _rag_documents_system_prompt_suffix()
    result = run_chat(
        message,
        history,
        system_prompt_suffix=build_chat_system_prompt_suffix(message, doc_index),
    )

    status = 200 if not result.get("error") else 502
    payload = dict(result)
    if not result.get("error"):
        payload["intent"] = classify_intent(message)
        payload["reference_downloads"] = reference_downloads_for_reply(
            request, result.get("reply") or ""
        )
    else:
        payload["reference_downloads"] = []
    return JsonResponse(payload, status=status)
