"""Gemini-compatible LangChain model configuration."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = "gemini-1.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def make_model(api_key: str, model_name: str = "") -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name or GEMINI_MODEL,
        api_key=api_key,
        base_url=GEMINI_BASE_URL,
        temperature=0.2,
        timeout=45,
        max_retries=1,
    )
