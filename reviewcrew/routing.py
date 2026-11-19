"""Intent detection and an explicit retrieval decision policy."""

import re

INTENT_RULES = {
    "debug": (r"\b(debug|bug|error|wrong|fix|crash|fail|broken)\b", "Find and explain likely defects."),
    "style": (r"\b(style|readab|format|naming|clean|pep.?8|lint)\b", "Focus on readability and conventions."),
    "explain": (r"\b(explain|walk ?through|understand|what does|how does)\b", "Explain behavior and structure."),
    "test": (r"\b(test|tests|testing|edge case|unit test|assert)\b", "Generate and optionally run checks."),
}


def detect_intent(request: str) -> tuple[str, str, float]:
    lowered = request.lower()
    for intent, (pattern, rationale) in INTENT_RULES.items():
        if re.search(pattern, lowered):
            return intent, rationale, 0.82
    return "review", "No specialized intent matched; run the complete review workflow.", 0.64


def should_retrieve(intent: str, request: str) -> tuple[bool, str]:
    if intent in {"debug", "style", "review", "test"}:
        return True, f"The {intent} route benefits from relevant Python review guidance."
    if intent == "explain" and re.search(r"\b(security|complex|performance|exception|input|edge)\b", request, re.I):
        return True, "This explanation request asks about a review topic where grounded guidance helps."
    return False, "A plain code walkthrough does not need external guidance."
