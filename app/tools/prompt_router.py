"""
Runtime intent classifier and per-intent **system-prompt suffix** fragments.

These strings are meant to be appended (after the main system instruction from
``vertex_chat``) together with the document catalog. The catalog block should
stay **last within that suffix** (after any intent fragment) so
``run_chat``’s citation checks still see ``## Documents in the retrieval corpus…``
in the suffix. The full Vertex system instruction appends a short closing
attribution section after the suffix.

Public API
----------
- ``classify_intent(message)`` — returns one of: factual, explain,
  creative, goal, general
- ``get_prompt_for_intent(intent)`` — short intent-specific guidance (empty for
  ``general``)
- ``build_chat_system_prompt_suffix(message, document_catalog)`` — intent
  appendix + source/catalog appendix, in the correct order
- ``INTENT_PROMPTS`` — dict mapping intent → suffix string
"""

from __future__ import annotations

import re

FACTUAL = "factual"
EXPLAIN = "explain"
CREATIVE = "creative"
GOAL = "goal"
GENERAL = "general"

# Ordered list: first match wins. Goal checked before creative/factual
# to catch personal-language questions like "I want to lose weight and
# know how many calories I should eat."
_PATTERNS: list[tuple[str, list[str]]] = [
    (GOAL, [
        r"\bi want to\b",
        r"\bi('m| am) trying to\b",
        r"\bmy goal\b",
        r"\blose weight\b",
        r"\bweight loss\b",
        r"\bbuild(ing)? muscle\b",
        r"\bgain(ing)? muscle\b",
        r"\beat (more )?healthier?\b",
        r"\bheart health\b",
        r"\b(manage|control|monitor|lower|track|improve) (my )?blood sugar\b",
        r"\bmy blood sugar\b",
        r"\bmanage (my )?(diabetes|cholesterol|weight)\b",
        r"\bget (more )?energy\b",
        r"\bimprove my (diet|health|nutrition)\b",
        r"\bbetter (diet|nutrition|eating)\b",
    ]),
    (CREATIVE, [
        r"\bwhat can i (make|cook|eat|do) with\b",
        r"\brecipes?\b",
        r"\bmeal ideas?\b",
        r"\bsubstitute for\b",
        r"\bswap (out )?\b",
        r"\bweeknight meals?\b",
        r"\bquick (and easy )?meals?\b",
        r"\bhealthy (snack|breakfast|lunch|dinner|dessert) ideas?\b",
        r"\bwhat (should i|can i) (make|cook|eat)\b",
        r"\bwhat('s| is) (a )?(good|healthy) (recipe|meal|dish)\b",
        r"\bhow (do i|to) (cook|prepare|make)\b",
    ]),
    (FACTUAL, [
        r"\bhow much\b",
        r"\bhow many (calories|grams?|mg|milligrams?|ounces?|servings?)\b",
        r"\bnutrition facts?\b",
        r"\bnutritional (value|info|information|content|profile)\b",
        r"\bwhat vitamins?\b",
        r"\bwhat minerals?\b",
        r"\bprotein in\b",
        r"\bcalories in\b",
        r"\bcarbs? in\b",
        r"\bfat in\b",
        r"\bsodium in\b",
        r"\bfiber in\b",
        r"\bgrams? of\b",
        r"\bvitamin [a-z]\d?\b",
        r"\bnutrients? (in|of|found)\b",
    ]),
    (EXPLAIN, [
        r"\bwhy (is|are|does|do|should)\b",
        r"\bhow does\b",
        r"\bhow do\b",
        r"\bwhat does .{1,40} do\b",
        r"\bexplain\b",
        r"\btell me (about|more about|why|how)\b",
        r"\bwhat (is|are) the (benefits?|effects?|role|purpose|function)\b",
        r"\bwhat happens (to|when|if)\b",
        r"\bdifference between\b",
        r"\bwhat is .{1,40} (good|bad|important|used) for\b",
    ]),
]


def classify_intent(message: str) -> str:
    """Return the intent for *message*. Never raises — defaults to GENERAL."""
    text = (message or "").lower()
    for intent, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                return intent
    return GENERAL


# ── Per-intent suffixes (append after main system prompt, before doc catalog) ─

INTENT_PROMPTS: dict[str, str] = {
    FACTUAL: """
## Response shape (factual)

Lead with the specific number or fact. Cite the USDA FoodData Central or Dietary
Guidelines source inline. Keep the answer concise — one to three sentences —
unless the user asks for more detail.
""".strip(),
    EXPLAIN: """
## Response shape (explain)

Structure your answer as: what it is → why it matters → how it practically helps
the user. Prefer analogies over jargon. End with one concrete, actionable takeaway.
""".strip(),
    CREATIVE: """
## Response shape (creative)

Offer 2–3 distinct, practical options formatted as a short list. Be enthusiastic and
concrete. Briefly note why each option is a nutritionally sound choice.
""".strip(),
    GOAL: """
## Response shape (goal)

Acknowledge the user's goal warmly first. Give 3 prioritized, actionable steps
tailored to that goal. Close by noting that individual needs vary and a registered
dietitian can help create a personalised plan.
""".strip(),
    # Main persona, tone, sources, citations, and goals live in ``vertex_chat`` default.
    GENERAL: "",
}


def get_prompt_for_intent(intent: str) -> str:
    """Return intent-specific guidance to append, or empty string for *general*."""
    return INTENT_PROMPTS.get(intent, INTENT_PROMPTS[GENERAL])


def build_chat_system_prompt_suffix(message: str, document_catalog: str) -> str:
    """
    Combine the **intent appendix** and **source appendix** (document catalog).

    When both are non-empty, the intent fragment comes first and the catalog
    stays last so the full system instruction still ends with the corpus block
    (required by the default prompt and by citation validation).
    """
    intent_part = get_prompt_for_intent(classify_intent(message))
    catalog = (document_catalog or "").strip()
    parts = [p for p in (intent_part.strip(), catalog) if p]
    return "\n\n".join(parts)
