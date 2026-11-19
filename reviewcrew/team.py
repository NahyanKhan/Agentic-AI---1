"""One structured LCEL call coordinating the review, fix, coach and test roles."""

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from reviewcrew.prompts import TEAM_SYSTEM, TEAM_USER
from reviewcrew.schemas import TeamReview


def run_review_team(model, *, intent: str, request: str, code: str, context: str, findings: str) -> TeamReview:
    parser = PydanticOutputParser(pydantic_object=TeamReview)
    prompt = ChatPromptTemplate.from_messages([
        ("system", TEAM_SYSTEM),
        ("human", TEAM_USER),
    ])
    chain = prompt | model | parser
    result = chain.invoke({
        "intent": intent,
        "request": request,
        "code": code,
        "context": context,
        "findings": findings,
        "format_instructions": parser.get_format_instructions(),
    })
    # Bound model output before the runner passes generated assertions to Docker.
    if len(result.tests) > 5:
        result.tests = result.tests[:5]
    for case in result.tests:
        case.assertion = case.assertion[:2000]
        case.name = case.name[:100]
        case.purpose = case.purpose[:300]
    result.corrected_code = result.corrected_code[:100_000]
    return result
