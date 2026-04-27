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
- ``run_chat(message, history, system_prompt_suffix=...)`` — send a turn to Gemini
  (optional *system_prompt_suffix* is appended to the configured system prompt,
  e.g. a catalog of user documents from your database)

Environment variables (via ``tools.env_config``):
  GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION, VERTEX_CHAT_MODEL,
  VERTEX_RAG_CORPUS (optional), VERTEX_RAG_TOP_K (optional, default 8).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

import vertexai
from google.api_core import exceptions as google_exceptions
from google.auth import exceptions as google_auth_exceptions
from vertexai import rag
from vertexai.generative_models import Content, GenerativeModel, Part, Tool

from tools.env_config import (
    EnvVarMissing,
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

You combine **general nutrition knowledge** (below) with **retrieved passages** from the user’s document library when retrieval returns them. If this prompt ends with a section titled **“Documents in the retrieval corpus (from your library)”**, treat that block as the authoritative catalog of what is indexed: each line’s **name** and **summary** tell you what may appear in RAG results—use those names when you cite user content (not raw file paths or chunk numbers).

### 1. Dietary Guidelines for Americans, 2020–2025 (USDA & HHS)
This is the official U.S. science-based guidance on healthy eating. Your advice should be grounded in its core principles: building a healthy dietary pattern with nutrient-dense foods, customizing choices to personal needs, and limiting items high in added sugars, saturated fat, and sodium. You should also be aware of its life-stage-specific recommendations and its recognition of various healthy eating patterns (e.g., U.S.-Style, Vegetarian, Mediterranean-Style). Use this source to explain *why* certain foods or habits are recommended.

---

### 2. USDA FoodData Central
Your knowledge is informed by this comprehensive source for food composition. You can provide detailed nutritional profiles for many basic and minimally processed foods, including macronutrients (protein, fat, carbohydrate), energy (kcal), fiber, sugars, key vitamins, and minerals.

Nutritional values are typically based on a standard 100g portion.

Use this source to answer questions like: "How much protein is in chicken?" or "What's a good source of potassium?" or "Which foods are high in fiber?"

---

### 3. User library (RAG corpus)

Retrieval may surface recipes, notes, or other uploads from the corpus. Prefer the **display names and summaries** from the appended catalog when they are present; when citing that material, refer to documents by those names, not internal filenames or chunk indices.

## Citation Requirements for Document-Based Answers

- When the prompt includes a document catalog section (``## Documents in the retrieval corpus (from your library)``), treat the response as document-based.
- For document-based responses, end with a natural source line in this format:
  ``Source: <document name>`` or ``Source: <doc 1>, <doc 2>``.
- If document support is missing or uncertain, say so clearly instead of guessing.

## Source lines for U.S. nutrition guidance

When you give **estimated macros**, **calories per meal**, or a **sample meal plan** from general knowledge (not only the user’s uploads), close the answer with a **Source:** line that names the references, for example:
``Source: Dietary Guidelines for Americans, 2020–2025; USDA FoodData Central``
If user-library content meaningfully shaped the answer, **append** those document display names (from the catalog, when present) to the same line after a comma or semicolon.

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

### Meal plans and macro breakdowns

When you sketch a sample day of eating, a meal plan, or the user asks for macros, go beyond calories alone: for **each meal/snack** and for the **daily total**, include **protein (g), carbohydrate (g), and fat (g)** at minimum (add **fiber (g)** when it helps). Use a small summary table or clearly labeled lines so the macros are easy to scan. Treat all numbers as **rounded estimates** for illustration unless you are citing a specific database-backed food line; remind the reader that needs vary by person, activity, and health status. Always finish with the **Source:** line described above so readers know which references the numbers draw from.

---

## What You Should NOT Do

- Do not diagnose, treat, or provide clinical guidance for specific medical conditions.
- Do not create personalized meal plans that prescribe exact calorie or macronutrient targets without noting that individual needs vary and a dietitian can help.
- Do not recommend dietary supplements as a substitute for food without noting the user should consult a healthcare provider.
- Do not make claims that any food cures or prevents disease.
- Do not shame or judge any food culture, dietary choice, or eating habit.

---

## Handling Uncertainty

If a specific food is not in the Foundation Foods dataset, say so honestly and offer the closest relevant comparison or general guidance from the Dietary Guidelines. If the user asks about content from their library and retrieval does not support an answer, say so rather than guessing. If a question is outside your knowledge, say so clearly and suggest the user consult a registered dietitian or their doctor.

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
# Full ``system_instruction`` string -> cached ``GenerativeModel`` (RAG tools match).
_model_cache: dict[str, GenerativeModel] = {}
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
        global _system_prompt, _model_cache
        _system_prompt = prompt.strip()
        _model_cache.clear()


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


def _effective_system_instruction(base: str, suffix: str) -> str:
    extra = (suffix or "").strip()
    if not extra:
        return base.strip()
    return f"{base.strip()}\n\n{extra}"


def _get_model(effective_system_instruction: str) -> GenerativeModel:
    """Return a cached model for this full system instruction text."""
    global _model_cache
    key = effective_system_instruction.strip()
    with _lock:
        cached = _model_cache.get(key)
        if cached is not None:
            return cached
        model = _build_model(key)
        _model_cache[key] = model
        return model


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
_SOURCE_LINE_PATTERN = re.compile(r"(?im)^\s*source:\s*(?P<sources>.+?)\s*$")
_NUMBERED_CITATION_PATTERN = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_DOC_CATALOG_MARKER = "## Documents in the retrieval corpus (from your library)"
_DOC_LINE_PATTERN = re.compile(r"^\s*-\s*(?P<name>[^:\n]+):", re.MULTILINE)
_CITATION_REQUIRED_ERROR = (
    "Document-based answers must end with `Source: <document name>` "
    "(or a comma-separated list of document names)."
)
_NUMBERED_CITATION_ERROR = (
    "Use a `Source: ...` line with document or guideline names, "
    "not numeric references such as [1]."
)

_STRUCTURED_NUTRITION_QUERY_PATTERN = re.compile(
    r"\b("
    r"meal\s*plans?|"
    r"sample\s*meal|"
    r"macro(s)?|"
    r"macro\s*breakdown|"
    r"break\s*down\s*(those|the)?\s*macro|"
    r"full[-\s]?day|"
    r"day\s*of\s*eating|"
    r"nutrition\s*breakdown"
    r")\b",
    re.IGNORECASE,
)

_STRUCTURED_NUTRITION_SOURCE_ERROR = (
    "For meal plans and macro breakdowns, end with a line such as: "
    "Source: Dietary Guidelines for Americans, 2020–2025; USDA FoodData Central "
    "(and add your library document names there if they informed the answer)."
)

_RETRYABLE_CODES = (
    429,   # RESOURCE_EXHAUSTED
    400,   # FailedPrecondition (RAG quota)
    503,   # UNAVAILABLE
)


def _metadata_get(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if obj.__class__.__module__.startswith("unittest.mock"):
            if name not in getattr(obj, "__dict__", {}):
                continue
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _metadata_items(obj: Any) -> list[tuple[str, Any]]:
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return []
    if isinstance(obj, dict):
        return list(obj.items())
    if isinstance(obj, (list, tuple, set)):
        return []
    if hasattr(obj, "items"):
        try:
            return list(obj.items())
        except (TypeError, ValueError):
            pass
    out: list[tuple[str, Any]] = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            continue
        out.append((name, value))
    return out


def _metadata_children(obj: Any) -> list[Any]:
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return []
    if isinstance(obj, (list, tuple, set)):
        return list(obj)
    return [value for _, value in _metadata_items(obj)]


def _string_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _looks_like_rag_resource(value: str) -> bool:
    return "/ragFiles/" in value or value.startswith("ragFiles/")


def _looks_like_gcs_uri(value: str) -> bool:
    return value.startswith("gs://")


def _source_ref_from_metadata_node(node: Any) -> dict[str, str]:
    fields = dict(_metadata_items(node))
    ref: dict[str, str] = {}

    for name in (
        "rag_resource_name",
        "ragResourceName",
        "rag_file",
        "ragFile",
        "resource_name",
        "resourceName",
        "source_resource",
        "sourceResource",
        "name",
    ):
        value = _string_value(fields.get(name))
        if value and _looks_like_rag_resource(value):
            ref["rag_resource_name"] = value
            break

    for name in ("gcs_uri", "gcsUri"):
        value = _string_value(fields.get(name))
        if value and _looks_like_gcs_uri(value):
            ref["gcs_uri"] = value
            break

    for name in ("uri", "source_uri", "sourceUri"):
        value = _string_value(fields.get(name))
        if not value:
            continue
        if _looks_like_rag_resource(value):
            ref.setdefault("rag_resource_name", value)
        elif _looks_like_gcs_uri(value):
            ref.setdefault("gcs_uri", value)
        else:
            ref.setdefault("uri", value)

    for name in (
        "title",
        "display_name",
        "displayName",
        "document_name",
        "documentName",
        "file_name",
        "fileName",
    ):
        value = _string_value(fields.get(name))
        if value:
            ref["display_name"] = value
            break

    return ref


def _source_ref_key(ref: dict[str, str]) -> tuple[str, str]:
    for name in ("rag_resource_name", "gcs_uri", "uri", "display_name"):
        value = (ref.get(name) or "").strip()
        if value:
            return (name, value.casefold())
    return ("", "")


def extract_grounded_source_refs(response: Any) -> list[dict[str, str]]:
    """
    Extract source identifiers from Vertex candidate metadata.

    Vertex grounding/citation schemas vary between SDK versions and retrieval
    backends, so this walks only candidate-level metadata containers and keeps
    source-looking fields. Missing metadata simply produces an empty list.
    """
    candidates = _metadata_get(response, "candidates") or []
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_ref(ref: dict[str, str]) -> None:
        ref = {k: v for k, v in ref.items() if v}
        key = _source_ref_key(ref)
        if not key[1] or key in seen:
            return
        seen.add(key)
        refs.append(ref)

    def walk(node: Any, depth: int = 0) -> None:
        if node is None or depth > 8:
            return
        if isinstance(node, (str, bytes, int, float, bool)):
            return
        if isinstance(node, (list, tuple, set)):
            for item in node:
                walk(item, depth + 1)
            return
        add_ref(_source_ref_from_metadata_node(node))
        for child in _metadata_children(node):
            walk(child, depth + 1)

    for candidate in candidates:
        for metadata in (
            _metadata_get(candidate, "grounding_metadata", "groundingMetadata"),
            _metadata_get(candidate, "citation_metadata", "citationMetadata"),
        ):
            walk(metadata)
    return refs


def _is_retryable(exc: google_exceptions.GoogleAPIError) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "grpc_status_code", None)
    msg = str(exc).lower()
    if code in _RETRYABLE_CODES:
        return True
    return "quota" in msg or "rate" in msg


def _requires_document_citation(system_prompt_suffix: str) -> bool:
    suffix = (system_prompt_suffix or "").strip()
    return _DOC_CATALOG_MARKER in suffix


def _extract_source_names(reply_text: str) -> list[str]:
    text = (reply_text or "").strip()
    match = _SOURCE_LINE_PATTERN.search(text)
    if not match:
        return []
    raw = (match.group("sources") or "").strip()
    if not raw:
        return []
    parts = re.split(r"[,;]", raw)
    return [chunk.strip().casefold() for chunk in parts if chunk.strip()]


def _source_line_tail(reply_text: str) -> str:
    text = (reply_text or "").strip()
    match = _SOURCE_LINE_PATTERN.search(text)
    if not match:
        return ""
    return (match.group("sources") or "").strip().casefold()


def _user_requests_structured_nutrition(message: str) -> bool:
    return bool(_STRUCTURED_NUTRITION_QUERY_PATTERN.search((message or "").strip()))


def _authority_sources_in_tail(tail: str) -> bool:
    if not tail:
        return False
    guides = (
        "dietary guideline" in tail
        or "guidelines for americans" in tail
        or ("guideline" in tail and "american" in tail)
    )
    data = "usda" in tail or "fooddata" in tail
    return guides and data


def _structured_nutrition_sources_ok(
    reply_text: str, system_prompt_suffix: str
) -> bool:
    tail = _source_line_tail(reply_text)
    if len(tail) < 8:
        return False
    known = set(_document_names_from_suffix(system_prompt_suffix))
    chunks = _extract_source_names(reply_text)
    if known:
        for c in chunks:
            if c in known:
                return True
    return _authority_sources_in_tail(tail)


def _has_numbered_citation(reply_text: str) -> bool:
    return bool(_NUMBERED_CITATION_PATTERN.search((reply_text or "").strip()))


def _document_names_from_suffix(system_prompt_suffix: str) -> list[str]:
    suffix = (system_prompt_suffix or "").strip()
    names: list[str] = []
    for match in _DOC_LINE_PATTERN.finditer(suffix):
        name = (match.group("name") or "").strip()
        if name:
            names.append(name.casefold())
    return names


def _reply_references_known_document(reply_text: str, system_prompt_suffix: str) -> bool:
    reply = (reply_text or "").casefold()
    if not reply:
        return False
    return any(name in reply for name in _document_names_from_suffix(system_prompt_suffix))


def _has_valid_source_line(reply_text: str, system_prompt_suffix: str) -> bool:
    source_names = _extract_source_names(reply_text)
    if not source_names:
        return False
    known_docs = set(_document_names_from_suffix(system_prompt_suffix))
    if not known_docs:
        return False
    return any(name in known_docs for name in source_names)


def run_chat(
    message: str,
    history: list[dict[str, Any]] | None = None,
    *,
    system_prompt_suffix: str = "",
) -> dict[str, Any]:
    """
    Send *message* (with optional multi-turn *history*) to Vertex Gemini.

    If *system_prompt_suffix* is non-empty, it is appended to the current
    system prompt (after a blank line) for this call only — useful for
    listing user-uploaded documents the RAG corpus may retrieve.

    Retries up to 3 times on transient quota / rate-limit errors.
    Returns ``{"reply": str, "error": str, "sources_used": list}``.
    """
    text = (message or "").strip()
    if not text:
        return {"reply": "", "error": "Message is required.", "sources_used": []}

    with _lock:
        base_prompt = _system_prompt
    effective = _effective_system_instruction(base_prompt, system_prompt_suffix)
    try:
        model = _get_model(effective)
    except EnvVarMissing as exc:
        return {"reply": "", "error": str(exc), "sources_used": []}
    contents = _build_contents(history, text)

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = model.generate_content(contents)
            break
        except (ValueError, RuntimeError) as exc:
            logger.exception("Configuration error")
            return {"reply": "", "error": str(exc), "sources_used": []}
        except google_auth_exceptions.DefaultCredentialsError:
            logger.warning("Application Default Credentials not found")
            return {
                "reply": "",
                "error": (
                    "Google Application Default Credentials are not set. "
                    "Run: gcloud auth application-default login"
                ),
                "sources_used": [],
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
            return {
                "reply": "",
                "error": f"AI service error: {detail}",
                "sources_used": [],
            }
    else:
        detail = getattr(last_exc, "message", None) or str(last_exc)
        return {
            "reply": "",
            "error": f"AI service error (after retries): {detail}",
            "sources_used": [],
        }

    if not response.candidates:
        return {
            "reply": "",
            "error": "No response from the model (blocked or empty).",
            "sources_used": [],
        }

    sources_used = extract_grounded_source_refs(response)

    try:
        reply_text = response.text or ""
    except ValueError:
        return {
            "reply": "",
            "error": "The model returned no text (safety filter or empty parts).",
            "sources_used": sources_used,
        }

    cleaned_reply = reply_text.strip()
    if _requires_document_citation(system_prompt_suffix) and _has_numbered_citation(
        cleaned_reply
    ):
        return {"reply": "", "error": _NUMBERED_CITATION_ERROR, "sources_used": sources_used}

    if (
        _requires_document_citation(system_prompt_suffix)
        and _reply_references_known_document(cleaned_reply, system_prompt_suffix)
        and not _has_valid_source_line(cleaned_reply, system_prompt_suffix)
    ):
        return {"reply": "", "error": _CITATION_REQUIRED_ERROR, "sources_used": sources_used}

    if _user_requests_structured_nutrition(text) and not _structured_nutrition_sources_ok(
        cleaned_reply, system_prompt_suffix
    ):
        return {
            "reply": "",
            "error": _STRUCTURED_NUTRITION_SOURCE_ERROR,
            "sources_used": sources_used,
        }

    return {"reply": cleaned_reply, "error": "", "sources_used": sources_used}
