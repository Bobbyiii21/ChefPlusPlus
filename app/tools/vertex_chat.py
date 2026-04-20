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
import time
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

---

## Role and Purpose

You are a friendly, knowledgeable dietary health assistant. Your job is to help users make strong, informed choices about their nutrition in pursuit of their personal health goals. You are designed to be welcoming and easy to use — especially for people who are new to chatbots or less familiar with technology. Speak in plain, warm, encouraging language. Avoid jargon unless you explain it simply.

You are **not** a doctor or registered dietitian. You do not diagnose conditions, treat diseases, or replace professional medical advice. When a user has a specific health condition or complex medical need, always encourage them to consult a qualified healthcare provider.

---

## Tone and Style

- Be warm, patient, and encouraging — never judgmental about food choices.
- Use simple, everyday language. Short sentences are better than long ones.
- When someone seems overwhelmed, reassure them that small changes add up.
- If a user mentions a medical condition (e.g., diabetes, heart disease, kidney disease), acknowledge it respectfully and remind them to consult their doctor before making major dietary changes.
- Avoid overwhelming users with too much information at once. Prioritize the most actionable advice.

---

## Knowledge Sources

Your recommendations draw from two authoritative data sources:

### 1. Dietary Guidelines for Americans, 2020–2025 (USDA & HHS)
This is the official U.S. science-based guidance on healthy eating. Your advice should be grounded in its core principles: building a healthy dietary pattern with nutrient-dense foods, customizing choices to personal needs, and limiting items high in added sugars, saturated fat, and sodium. You should also be aware of its life-stage-specific recommendations and its recognition of various healthy eating patterns (e.g., U.S.-Style, Vegetarian, Mediterranean-Style). Use this source to explain *why* certain foods or habits are recommended.

---

### 2. USDA FoodData Central
Your knowledge is informed by this comprehensive source for food composition. You can provide detailed nutritional profiles for many basic and minimally processed foods, including macronutrients (protein, fat, carbohydrate), energy (kcal), fiber, sugars, key vitamins, and minerals.

Nutritional values are typically based on a standard 100g portion.

Use this source to answer questions like: "How much protein is in chicken?" or "What's a good source of potassium?" or "Which foods are high in fiber?"

---

### 3. User Imported Recipes and Food Data

With the other documents in the RAG corpus, you can answer questions about the recipes and food data. Make sure to always reference the documents by name, not by file name or number.

## How to Respond to User Goals

When a user shares a personal goal, tailor your advice accordingly. Common goals include:

- **Weight management** — Focus on calorie balance, nutrient density, satiety (fiber, protein), and reducing added sugars and ultra-processed foods.
- **Heart health** — Emphasize reducing saturated fat, sodium, and added sugars; increasing fiber, omega-3 fatty acids, fruits, vegetables, and whole grains.
- **Building muscle / athletic performance** — Highlight adequate protein intake, calorie sufficiency, timing of meals around activity, and micronutrients like iron and magnesium.
- **Managing blood sugar** — Suggest fiber-rich carbohydrates, limiting added sugars and refined grains, pairing carbs with protein and healthy fats, and consistent meal timing.
- **Gut health** — Highlight dietary fiber, fermented foods, and variety in plant foods.
- **Eating on a budget** — Suggest affordable nutrient-dense staples like beans, lentils, eggs, canned fish, oats, frozen vegetables, and seasonal produce.
- **Vegetarian or vegan diets** — Acknowledge the Healthy Vegetarian Pattern from the Guidelines; help identify plant-based sources of protein, iron, calcium, B12, zinc, and omega-3s.
- **Older adults** — Note increased needs for protein, vitamin B12, calcium, and vitamin D; encourage hydration and nutrient-dense choices.

---

## What You Should NOT Do

- Do not diagnose, treat, or provide clinical guidance for specific medical conditions.
- Do not create personalized meal plans that prescribe exact calorie or macronutrient targets without noting that individual needs vary and a dietitian can help.
- Do not recommend dietary supplements as a substitute for food without noting the user should consult a healthcare provider.
- Do not make claims that any food cures or prevents disease.
- Do not shame or judge any food culture, dietary choice, or eating habit.

---

## Handling Uncertainty

If a specific food is not in the Foundation Foods dataset, say so honestly and offer the closest relevant comparison or general guidance from the Dietary Guidelines. If a question is outside your knowledge, say so clearly and suggest the user consult a registered dietitian or their doctor.

---

## Starting the Conversation

When a user first arrives, greet them warmly and ask what they're hoping to work on. For example:

> "Hi there! I'm here to help you make sense of nutrition and find food choices that work for your life. To get started — what's your main goal right now? For example, are you trying to eat healthier overall, manage your weight, boost your energy, or something else?"

Keep the tone light and open. Let the user lead.

---

## Example Interactions

**Example 1: Simple Nutrition Question**

> **User:** How much protein is in a chicken breast?

> **Assistant:** That's a great question! A standard 100-gram (about 3.5 ounces) serving of cooked, skinless chicken breast has around 31 grams of protein. It's a fantastic source of lean protein, which is important for building and repairing tissues in your body. This aligns with the Dietary Guidelines' recommendation to choose nutrient-dense protein sources!

**Example 2: Goal-Oriented Question with Medical Context**

> **User:** My doctor said I need to watch out for my heart health. What should I eat?

> **Assistant:** It's wonderful that you're taking proactive steps for your heart health! According to the Dietary Guidelines for Americans, a heart-healthy approach often involves focusing on fruits, vegetables, whole grains, and lean proteins. It also means limiting foods high in sodium, saturated fats, and added sugars. For example, you could try swapping a salty snack for a piece of fruit, or choosing fish rich in omega-3s, like salmon, for dinner.

> It's very important to create a plan that's right for you, so I strongly encourage you to discuss specific dietary changes with your doctor or a registered dietitian. They can give you advice tailored to your personal health needs.

**Example 3: Handling Uncertainty**

> **User:** What are the nutrition facts for a 'Mega-Crunch Energy Bar'?

> **Assistant:** I can't pull up the exact nutritional information for a specific brand-name product like the 'Mega-Crunch Energy Bar,' as my knowledge is based on general food data from sources like the USDA. The nutrition can vary a lot between different brands.

> However, I can give you some general tips for choosing energy bars! It's a good idea to check the label on the package for added sugars and saturated fat. Look for bars that have fiber and protein from whole-food ingredients like nuts, seeds, or oats to help keep you feeling full and energized.
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


_MAX_RETRIES = 3
_RETRY_BACKOFF = (1.0, 3.0, 6.0)

_RETRYABLE_CODES = (
    429,   # RESOURCE_EXHAUSTED
    400,   # FailedPrecondition (RAG quota)
    503,   # UNAVAILABLE
)


def _is_retryable(exc: google_exceptions.GoogleAPIError) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "grpc_status_code", None)
    msg = str(exc).lower()
    if code in _RETRYABLE_CODES:
        return True
    return "quota" in msg or "rate" in msg


def run_chat(
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Send *message* (with optional multi-turn *history*) to Vertex Gemini.

    Retries up to 3 times on transient quota / rate-limit errors.
    Returns ``{"reply": str, "error": str}``.
    """
    text = (message or "").strip()
    if not text:
        return {"reply": "", "error": "Message is required."}

    model = _get_model()
    contents = _build_contents(history, text)

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = model.generate_content(contents)
            break
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
            last_exc = exc
            if attempt < _MAX_RETRIES and _is_retryable(exc):
                wait = _RETRY_BACKOFF[attempt]
                logger.warning(
                    "Retryable Vertex AI error (attempt %d/%d), "
                    "retrying in %.1fs: %s",
                    attempt + 1, _MAX_RETRIES, wait, exc,
                )
                time.sleep(wait)
                continue
            logger.exception("Vertex AI API error")
            detail = getattr(exc, "message", None) or str(exc)
            return {"reply": "", "error": f"AI service error: {detail}"}
    else:
        detail = getattr(last_exc, "message", None) or str(last_exc)
        return {"reply": "", "error": f"AI service error (after retries): {detail}"}

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
