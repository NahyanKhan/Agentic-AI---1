"""Optional LangChain chat model setup and LCEL call helpers."""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


def make_model(provider: str, model_name: str, api_key: str = "", base_url: str = ""):
    if provider == "Ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_name, temperature=0.2)
    from langchain_openai import ChatOpenAI
    options = {"model": model_name, "api_key": api_key, "temperature": 0.2}
    if base_url.strip():
        options["base_url"] = base_url.strip()
    return ChatOpenAI(**options)


def lcel(prompt: ChatPromptTemplate, model, **values) -> str:
    chain = prompt | model | StrOutputParser()
    return chain.invoke(values)
