"""Comprehensive verification tests for ReviewCrew Code Review & Debug Squad."""

import ast

from reviewcrew.analyzer import Finding, analyze, generate_fallback_tests, score
from reviewcrew.knowledge import GUIDANCE, documents
from reviewcrew.linter import lint_python
from reviewcrew.models import (
    GEMINI_BASE_URL,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MODEL,
    make_model,
)
from reviewcrew.routing import detect_intent, should_retrieve
from reviewcrew.runner import run_cases
from reviewcrew.schemas import GeneratedTest, ReviewFinding, TeamReview


def test_analyzer_detects_planted_defects():
    sample = """def average(values=[]):
    try:
        total = sum(values)
        return total / len(values)
    except Exception:
        return 0

def normalizeName(Name):
    f = open('test.txt')
    return eval(Name)
"""
    findings, tree, err = analyze(sample)
    assert err is None
    assert tree is not None
    messages = [f.message for f in findings]
    categories = {f.category for f in findings}

    # Verify Bug Finder detections
    assert any("Mutable default" in m for m in messages), "Failed to detect mutable default"
    assert any("Division by `len(...)`" in m for m in messages), "Failed to detect division by len"
    assert any("Broad `except Exception:`" in m for m in messages), "Failed to detect broad except"
    assert any("eval()" in m for m in messages), "Failed to detect eval"
    assert any("File opened without a `with`" in m for m in messages), "Failed to detect open outside with"
    assert any("not snake_case" in m for m in messages), "Failed to detect camelCase function"

    assert "Correctness" in categories
    assert "Security" in categories
    assert "Reliability" in categories
    assert "Style" in categories


def test_analyzer_detects_division_by_zero():
    code = "def bad_math():\n    return 42 / 0\n"
    findings, _, _ = analyze(code)
    assert any("Division by zero" in f.message for f in findings)


def test_scorer_calibration():
    # Clean code: score 100
    clean_findings = []
    scores = score(clean_findings)
    assert scores["Overall"] == 100
    assert scores["Correctness"] == 100
    assert scores["Style"] == 100

    # Code with errors
    bad_findings = [
        Finding("high", "Correctness", "Bug 1"),
        Finding("high", "Security", "Eval 1"),
        Finding("low", "Style", "Style 1"),
    ]
    bad_scores = score(bad_findings)
    assert bad_scores["Correctness"] < 100
    assert bad_scores["Overall"] < 100
    assert bad_scores["Style"] < 100


def test_linter_ruff():
    code = "def foo():\n    x = 1\n    return 2\n"
    findings, err = lint_python(code)
    assert err is None
    # x = 1 is unused (F841)
    assert any("F841" in f.message for f in findings)


def test_intent_router_classifications():
    cases = [
        ("Find bugs and fix issues in my code", "debug"),
        ("Debug this function", "debug"),
        ("Why is this crashing on error?", "debug"),
        ("Check the style and formatting conventions", "style"),
        ("Ensure PEP8 naming compliance", "style"),
        ("Explain how this function works", "explain"),
        ("Walk through this algorithm", "explain"),
        ("Generate behavior unit tests", "test"),
        ("Write assertions for edge cases", "test"),
        ("Give a general review of this module", "review"),
    ]
    for prompt, expected_intent in cases:
        intent, rationale, conf = detect_intent(prompt)
        assert intent == expected_intent, f"Prompt '{prompt}' routed to '{intent}' instead of '{expected_intent}'"
        assert conf > 0.5


def test_retrieval_policy():
    # Debug, style, review, test should trigger RAG
    assert should_retrieve("debug", "find bugs")[0] is True
    assert should_retrieve("style", "check style")[0] is True
    assert should_retrieve("review", "full review")[0] is True
    assert should_retrieve("test", "write tests")[0] is True

    # Plain walkthrough without technical keywords should skip RAG
    assert should_retrieve("explain", "tell me what this does")[0] is False
    # Walkthrough asking about exceptions/security should trigger RAG
    assert should_retrieve("explain", "explain security issues in input")[0] is True


def test_knowledge_base_sources():
    docs = documents()
    assert len(docs) == len(GUIDANCE)
    assert len(docs) >= 15
    for doc in docs:
        assert "source" in doc.metadata
        assert doc.metadata["source"].startswith("http")
        assert len(doc.page_content) > 20


def test_fallback_tests_generation():
    code = "def add(a, b): return a + b\ndef greet(): return 'hi'\n"
    tree = ast.parse(code)
    fallback = generate_fallback_tests(tree)
    assert len(fallback) == 2
    names = [t["name"] for t in fallback]
    assert "test_add_signature" in names
    assert "test_greet_no_args" in names


def test_pydantic_schemas():
    test_obj = GeneratedTest(
        name="test_avg_normal",
        assertion="assert average([2, 4]) == 3.0",
        purpose="Verify normal calculation",
    )
    finding_obj = ReviewFinding(
        severity="high",
        category="Correctness",
        message="ZeroDivisionError",
        line=4,
        suggestion="Check len",
    )
    review_obj = TeamReview(
        summary="Test summary",
        findings=[finding_obj],
        coaching="Test coaching",
        corrected_code="def average(values=None): ...",
        tests=[test_obj],
    )
    dumped = review_obj.model_dump()
    assert dumped["summary"] == "Test summary"
    assert len(dumped["tests"]) == 1
    assert len(dumped["findings"]) == 1


def test_runner_docker_diagnostic_guidance():
    # If Docker daemon is stopped, run_cases must provide diagnostic guidance and NOT execute on host
    dummy_cases = [{"name": "test_1", "assertion": "assert True"}]
    res = run_cases("x = 1", dummy_cases)
    assert isinstance(res, dict)
    assert "passed" in res
    assert "returncode" in res
    assert "stderr" in res
    if not res["passed"]:
        assert any(keyword in res["stderr"].lower() for keyword in ("docker", "sandbox", "image", "daemon", "timed out"))


def test_model_configuration():
    assert GEMINI_BASE_URL == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert GEMINI_MODEL == "gemini-2.5-flash"
    assert GEMINI_FALLBACK_MODEL == "gemini-1.5-flash"
    m = make_model("fake-api-key")
    assert m.model_name == "gemini-2.5-flash"
    assert m.temperature == 0.2
