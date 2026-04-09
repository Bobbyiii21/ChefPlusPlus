"""
Vertex AI (Gemini) chat for the dietary assistant, with optional Vertex RAG Engine
retrieval when VERTEX_RAG_CORPUS is set (full corpus resource name).

Environment (aligned with infrastructure/terraform/cloudrun.tf):
  GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION, VERTEX_CHAT_MODEL,
  GCS_KNOWLEDGE_BUCKET (for ops / uploads; RAG queries use the corpus),
  VERTEX_RAG_CORPUS (optional), VERTEX_RAG_TOP_K (optional, default 8).

Terraform default for VERTEX_CHAT_MODEL: gemini-3.1-flash-lite-preview (Gemini 3.1 Flash-Lite on Vertex).
For Gemini 3 Flash (non-Lite): set vertex_chat_model to gemini-3-flash-preview.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import vertexai
from google.api_core import exceptions as google_exceptions
from google.auth import exceptions as google_auth_exceptions
from vertexai import rag
from vertexai.generative_models import Content, GenerativeModel, Part, Tool

logger = logging.getLogger(__name__)

# Full system instruction for the product assistant (Dietary Health Assistant).
DIETARY_HEALTH_SYSTEM_INSTRUCTION = """
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


class AssistantConfigurationError(RuntimeError):
    """Missing or invalid environment configuration for Vertex AI."""


def _env_project() -> str:
    project = (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    if not project:
        raise AssistantConfigurationError(
            "GOOGLE_CLOUD_PROJECT is not set (required for Vertex AI)."
        )
    return project


def _env_location() -> str:
    loc = (
        os.environ.get("VERTEX_AI_LOCATION")
        or os.environ.get("GCP_REGION")
        or "us-central1"
    ).strip()
    return loc


def _env_model_id() -> str:
    mid = (os.environ.get("VERTEX_CHAT_MODEL") or "").strip()
    if not mid:
        raise AssistantConfigurationError(
            "VERTEX_CHAT_MODEL is not set (Terraform passes this from var.vertex_chat_model)."
        )
    return mid


def _env_rag_corpus() -> str | None:
    corpus = (os.environ.get("VERTEX_RAG_CORPUS") or "").strip()
    return corpus or None


def _env_rag_top_k() -> int:
    raw = (os.environ.get("VERTEX_RAG_TOP_K") or "8").strip()
    try:
        top_k = int(raw)
    except ValueError:
        return 8
    return max(1, min(top_k, 32))


@lru_cache(maxsize=1)
def _vertex_initialized_key() -> tuple[str, str]:
    project = _env_project()
    location = _env_location()
    vertexai.init(project=project, location=location)
    logger.info("vertexai.init project=%s location=%s", project, location)
    return project, location


def _build_generative_model() -> GenerativeModel:
    _vertex_initialized_key()
    model_id = _env_model_id()
    corpus = _env_rag_corpus()
    top_k = _env_rag_top_k()

    kwargs: dict[str, Any] = {
        "model_name": model_id,
        "system_instruction": DIETARY_HEALTH_SYSTEM_INSTRUCTION,
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
            "VERTEX_RAG_CORPUS is unset; using Gemini without retrieval. "
            "Index GCS_KNOWLEDGE_BUCKET into a Vertex RAG corpus and set VERTEX_RAG_CORPUS."
        )

    return GenerativeModel(**kwargs)


@lru_cache(maxsize=1)
def _get_model() -> GenerativeModel:
    return _build_generative_model()


def _contents_from_history(
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


def run_dietary_assistant_chat(
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Call Vertex Gemini (with optional RAG tool). Returns
    {"reply": str} on success or {"error": str, "reply": ""} on failure.
    """
    text = (message or "").strip()
    if not text:
        return {"reply": "", "error": "Message is required."}

    try:
        model = _get_model()
        contents = _contents_from_history(history, text)
        response = model.generate_content(contents)
    except AssistantConfigurationError as exc:
        logger.exception("Assistant configuration error")
        return {"reply": "", "error": str(exc)}
    except google_auth_exceptions.DefaultCredentialsError:
        logger.warning("Application Default Credentials not found")
        return {
            "reply": "",
            "error": (
                "Google Application Default Credentials are not set. "
                "Run: gcloud auth application-default login "
                "(uses your user account for local dev; Cloud Run uses its service account)."
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
