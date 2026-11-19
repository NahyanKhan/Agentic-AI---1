"""Intent detection and an explicit retrieval decision policy."""

from __future__ import annotations

import re

INTENT_RULES = {
    "debug": (
        r"\b(debug|debugger|debugging|bug|bugs|error|errors|wrong|fix|fixes|fixing|crash|crashes|crashing|fail|fails|failed|failing|failure|failures|broken|break|breaks|defect|defects|issue|issues)\b",
        "Find and explain likely defects.",
    ),
    "style": (
        r"\b(style|styling|readab\w*|format|formatting|naming|name|names|clean|pep.?8|lint|linter|linting|convention|conventions)\b",
        "Focus on readability and conventions.",
    ),
    "explain": (
        r"\b(explain|explaining|explanation|walk ?through|understand|understanding|what does|how does|why does|document|docstring)\b",
        "Explain behavior and structure.",
    ),
    "test": (
        r"\b(test|tests|testing|test-case|test-cases|edge[- ]case|edge[- ]cases|unit[- ]test|unit[- ]tests|assert|assertion|assertions|verify|verification)\b",
        "Generate and optionally run checks.",
    ),
}


def detect_intent(request: str) -> tuple[str, str, float]:
    lowered = request.lower()
    for intent, (pattern, rationale) in INTENT_RULES.items():
        if re.search(pattern, lowered):
            return intent, rationale, 0.85
    return "review", "No specialized intent matched; run the complete review workflow.", 0.65


def should_retrieve(intent: str, request: str) -> tuple[bool, str]:
    if intent in {"debug", "style", "review", "test"}:
        return True, f"The {intent} route benefits from relevant Python review guidance."
    if intent == "explain" and re.search(r"\b(security|complex|performance|exception|input|edge|error|bug)\b", request, re.I):
        return True, "This explanation request asks about a review topic where grounded guidance helps."
    return False, "A plain code walkthrough does not need external guidance."
