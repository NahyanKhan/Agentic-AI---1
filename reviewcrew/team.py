"""One structured LCEL call coordinating the review, fix, coach and test roles."""

from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from reviewcrew.models import GEMINI_FALLBACK_MODEL, make_model
from reviewcrew.prompts import TEAM_SYSTEM, TEAM_USER
from reviewcrew.schemas import TeamReview


def run_review_team(model, *, intent: str, request: str, code: str, context: str, findings: str) -> TeamReview:
    parser = PydanticOutputParser(pydantic_object=TeamReview)
    prompt = ChatPromptTemplate.from_messages([
        ("system", TEAM_SYSTEM),
        ("human", TEAM_USER),
    ])
    chain = prompt | model | parser
    invoke_args = {
        "intent": intent,
        "request": request,
        "code": code,
        "context": context,
        "findings": findings,
        "format_instructions": parser.get_format_instructions(),
    }

    try:
        result = chain.invoke(invoke_args)
    except Exception as exc:
        err_msg = str(exc).lower()
        # If the requested model is not found (404), retry with the universal fallback model
        if ("404" in err_msg or "not found" in err_msg) and hasattr(model, "model_name") and model.model_name != GEMINI_FALLBACK_MODEL:
            api_key = model.openai_api_key.get_secret_value() if hasattr(model.openai_api_key, "get_secret_value") else str(model.openai_api_key)
            fallback_model = make_model(api_key=api_key, model_name=GEMINI_FALLBACK_MODEL)
            fallback_chain = prompt | fallback_model | parser
            result = fallback_chain.invoke(invoke_args)
        else:
            raise

    # Bound model output before the runner passes generated assertions to Docker.
    if len(result.tests) > 5:
        result.tests = result.tests[:5]
    for case in result.tests:
        case.assertion = case.assertion[:2000]
        case.name = case.name[:100]
        case.purpose = case.purpose[:300]
    result.corrected_code = result.corrected_code[:100_000]
    return result
