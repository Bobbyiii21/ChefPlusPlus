import json

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
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

    from tools.vertex_chat import run_chat

    doc_index = _rag_documents_system_prompt_suffix()
    result = run_chat(
        message,
        history,
        system_prompt_suffix=doc_index,
    )

    status = 200 if not result.get("error") else 502
    return JsonResponse(result, status=status)
