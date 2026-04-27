import json
import time

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


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
    from developer.models import QueryLog

    start = time.time()
    result = run_chat(message, history)
    elapsed = int((time.time() - start) * 1000)

    user = request.user if request.user.is_authenticated else None
    QueryLog.objects.create(
        user=user,
        response_time_ms=elapsed,
        success=not result.get("error"),
    )

    status = 200 if not result.get("error") else 502
    return JsonResponse(result, status=status)
