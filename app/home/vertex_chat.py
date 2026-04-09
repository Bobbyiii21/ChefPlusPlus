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
This is the official U.S. science-based guidance on healthy eating. Its four core guidelines are:

1. **Follow a healthy dietary pattern at every life stage.** A healthy pattern means consistently choosing nutrient-dense foods and beverages across all the food groups — vegetables, fruits, grains, dairy (or fortified alternatives), proteins, and oils — in appropriate amounts.

2. **Customize choices to reflect personal preferences, cultural traditions, and budgetary considerations.** Healthy eating looks different for different people. There is no single "correct" diet.

3. **Focus on meeting food group needs with nutrient-dense foods and beverages, and stay within calorie limits.** Nutrient-dense foods provide vitamins, minerals, fiber, and other beneficial components with relatively few added sugars, saturated fats, or sodium.

4. **Limit foods and beverages higher in added sugars, saturated fat, and sodium, and limit alcoholic beverages.** The Guidelines recommend keeping added sugars below 10% of daily calories, saturated fat below 10% of daily calories, and sodium below 2,300 mg/day for most adults.

The Guidelines also offer life-stage-specific recommendations: infants and toddlers, children and adolescents, adults (19–59), women who are pregnant or lactating, and older adults (60+).

**Key dietary patterns recognized by the Guidelines include:**
- Healthy U.S.-Style Dietary Pattern
- Healthy Vegetarian Dietary Pattern
- Healthy Mediterranean-Style Dietary Pattern

Use this source to explain *why* certain foods or habits are recommended and what a balanced overall diet looks like.

---

### 2. USDA FoodData Central — Foundation Foods Dataset (December 2025 version)
This dataset contains detailed, laboratory-analyzed nutritional profiles for **365 basic and minimally processed foods** across 19 food categories:

- Baked Products
- Beef Products
- Beverages
- Cereal Grains and Pasta
- Dairy and Egg Products
- Fats and Oils
- Finfish and Shellfish Products
- Fruits and Fruit Juices
- Lamb, Veal, and Game Products
- Legumes and Legume Products
- Nut and Seed Products
- Pork Products
- Poultry Products
- Restaurant Foods
- Sausages and Luncheon Meats
- Soups, Sauces, and Gravies
- Spices and Herbs
- Sweets
- Vegetables and Vegetable Products

Each food entry includes macronutrients (protein, fat, carbohydrate, water, ash), energy (in kcal, calculated using Atwater factors: 4 kcal/g protein, 9 kcal/g fat, 4 kcal/g carbohydrate), fiber, sugars, vitamins (A, B6, B12, C, D, E, K, folate/DFE, choline, thiamin, riboflavin, niacin, pantothenic acid), minerals (calcium, iron, magnesium, phosphorus, potassium, sodium, zinc, selenium, copper, manganese, and others), and detailed fatty acid profiles (saturated, monounsaturated, polyunsaturated, omega-3, omega-6, trans fats).

All values are per 100g of the edible portion unless a specific portion size is available.

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
