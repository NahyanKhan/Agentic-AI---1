"""Gemini-compatible LangChain model configuration."""

GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def make_model(api_key: str):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=GEMINI_MODEL,
        api_key=api_key,
        base_url=GEMINI_BASE_URL,
        temperature=0.2,
        timeout=45,
        max_retries=0,
    )
