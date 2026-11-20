from __future__ import annotations

import json
import re
from datetime import datetime

import keyring
import streamlit as st
from langchain_core.output_parsers import PydanticOutputParser

from reviewcrew.analyzer import Finding, analyze, generate_fallback_tests, score
from reviewcrew.linter import lint_python
from reviewcrew.models import make_model
from reviewcrew.prompts import TEAM_SYSTEM, TEAM_USER
from reviewcrew.retrieval import open_store, retrieve
from reviewcrew.routing import detect_intent, should_retrieve
from reviewcrew.runner import run_cases
from reviewcrew.schemas import TeamReview
from reviewcrew.team import run_review_team

GEMINI_KEYRING_SERVICE = "ReviewCrew"
GEMINI_KEYRING_ACCOUNT = "gemini-api-key"


def read_saved_api_key() -> str:
    try:
        return keyring.get_password(GEMINI_KEYRING_SERVICE, GEMINI_KEYRING_ACCOUNT) or ""
    except Exception:
        return ""


def save_api_key(api_key: str) -> bool:
    try:
        keyring.set_password(GEMINI_KEYRING_SERVICE, GEMINI_KEYRING_ACCOUNT, api_key)
        return True
    except Exception:
        return False


def extract_python_code(text: str) -> str:
    """Extract clean Python code from model output, stripping markdown fences if present."""
    text = (text or "").strip()
    match = re.search(r"```(?:python)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return text


@st.cache_resource(show_spinner=False)
def cached_knowledge_store():
    """Load the embedding model and Chroma collection once per app process."""
    return open_store()


st.set_page_config(
    page_title="ReviewCrew · Agentic Code Review",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.block-container { padding-top: 2rem; max-width: 1440px; }
.hero { padding: 1.25rem 0 1.6rem; border-bottom: 1px solid #26343a; margin-bottom: 1.6rem; }
.eyebrow { color:#9CF2CF; letter-spacing:.15em; text-transform:uppercase; font:500 .72rem 'DM Mono',monospace; }
.hero h1 { font-size:2.35rem; line-height:1.1; margin:.45rem 0; letter-spacing:-.045em; }
.hero p { color:#9aaeb2; margin:0; max-width:720px; }
.agent { border:1px solid #26343a; border-radius:12px; padding:14px 15px; min-height:105px; background:#111a1f; }
.agent-title { color:#9CF2CF; font:500 .7rem 'DM Mono',monospace; text-transform:uppercase; letter-spacing:.08em; }
.agent-copy { color:#b2c0c1; font-size:.86rem; margin-top:8px; }
.metric { border-left:2px solid #9CF2CF; padding-left:12px; }
.metric-label { font:500 .68rem 'DM Mono',monospace; color:#8ba0a3; text-transform:uppercase; }
.metric-value { font-size:1.65rem; font-weight:700; }
div[data-testid="stCode"] { border:1px solid #26343a; }
</style>
<div class="hero"><div class="eyebrow">Agentic AI · Engineering Review Lab</div>
<h1>Good code gets sharper<br>with a second set of eyes.</h1>
<p>Four focused agents review your Python, retrieve relevant guidance, and turn findings into a clear next step.</p></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ◈ ReviewCrew")
    st.caption("A multi-agent Python review desk")
    st.divider()
    saved_api_key = read_saved_api_key()
    api_key = st.text_input(
        "Gemini API key",
        value=saved_api_key,
        type="password",
        help="Saved securely in this computer's credential manager for future launches. Never committed or logged.",
        key="gemini_api_key",
    ).strip()
    key_save_failed = bool(api_key and api_key != saved_api_key and not save_api_key(api_key))
    if key_save_failed:
        st.warning("The key works for this session, but this computer could not save it securely for next time.")
    st.divider()
    st.markdown("**Review route**")
    route_choice = st.selectbox(
        "Choose an intent",
        ["Auto-detect", "Full review", "Debug", "Style review", "Explain", "Generate tests"],
        label_visibility="collapsed",
    )
    run_tests = st.checkbox(
        "Run generated assertions in Docker",
        value=True,
        help="Runs generated behavior tests in a disposable Docker container with no network, a read-only filesystem, and resource limits. Requires Docker Desktop.",
    )
    st.divider()
    st.caption("Local corpus · ChromaDB · LCEL")

AGENTS = [
    ("01 · Bug Finder", "AST and Gemini checks look for logic, boundary, and runtime risks."),
    ("02 · Style Reviewer", "Ruff checks Python conventions alongside code readability."),
    ("03 · Fixer", "Suggests a complete corrected program using findings and retrieved guidance."),
    ("04 · Test Writer", "Creates behavior tests and can run them in an isolated container."),
]
cols = st.columns(4)
for col, (title, copy) in zip(cols, AGENTS, strict=False):
    col.markdown(f'<div class="agent"><div class="agent-title">{title}</div><div class="agent-copy">{copy}</div></div>', unsafe_allow_html=True)

left, right = st.columns([1.12, 0.88], gap="large")
with left:
    st.markdown("#### Your code")
    sample = '''def average(values=[]):
    try:
        total = sum(values)
        return total / len(values)
    except Exception:
        return 0

def normalizeName(Name):
    return eval(Name)
'''
    code = st.text_area(
        "Python source",
        value=sample,
        height=350,
        label_visibility="collapsed",
        help="Paste a Python snippet. Avoid secrets and proprietary code when using a remote API.",
    )
    request = st.text_input(
        "What should the team focus on?",
        value="Review this code and suggest fixes for bugs and safety risks.",
        placeholder="e.g. Find edge cases and explain how to fix them",
    )
    run = st.button("Run agent review  →", type="primary", use_container_width=True)
    st.caption("Python only · Findings combine AST, Ruff, and Gemini review")

with right:
    st.markdown("#### Review report")
    if run:
        intents = {
            "Full review": "review",
            "Debug": "debug",
            "Style review": "style",
            "Explain": "explain",
            "Generate tests": "test",
        }
        model = None
        model_error = None
        rag_error = None
        lint_error = None
        docs = []

        with st.status("Starting the review team…", expanded=True) as progress:
            if api_key:
                try:
                    model = make_model(api_key)
                except Exception as exc:
                    model_error = f"Gemini setup failed ({type(exc).__name__})."

            progress.write("Routing your request…")
            if route_choice == "Auto-detect":
                intent, rationale, confidence = detect_intent(request)
            else:
                intent, rationale, confidence = intents[route_choice], "Intent selected explicitly in the sidebar.", 1.0

            do_retrieve, retrieval_reason = should_retrieve(intent, request)
            progress.write("Checking the code and style…")
            findings, tree, syntax_error = analyze(code)
            lint_findings, lint_error = lint_python(code)
            findings.extend(lint_findings)
            scores = score(findings)

            if do_retrieve:
                progress.write("Loading related coding guidance…")
                try:
                    store = cached_knowledge_store()
                    # Keep the embedding query short; the full code and findings
                    # are still included in the Gemini review prompt below.
                    docs = retrieve(store, f"{intent}: {request}\n{code[:800]}", k=2)
                except Exception as exc:
                    rag_error = f"Knowledge retrieval failed ({type(exc).__name__}). Install requirements and retry."

            context = "\n".join(
                f"- {d.page_content} [Source: {d.metadata.get('source', 'ReviewCrew guide')}]"
                for d in docs
            ) or "No retrieved guidance available."

            model_review = None
            rendered_user_prompt = ""
            if model and not syntax_error:
                progress.write("Gemini review running. This usually finishes within 30 seconds…")
                try:
                    parser = PydanticOutputParser(pydantic_object=TeamReview)
                    rendered_user_prompt = TEAM_USER.format(
                        intent=intent,
                        request=request,
                        context=context,
                        findings=json.dumps([f.as_dict() for f in findings], ensure_ascii=False),
                        code=code,
                        format_instructions=parser.get_format_instructions(),
                    )
                    model_review = run_review_team(
                        model,
                        intent=intent,
                        request=request,
                        code=code,
                        context=context,
                        findings=json.dumps([f.as_dict() for f in findings], ensure_ascii=False),
                    )
                    model_findings = [Finding(**item.model_dump()) for item in model_review.findings]
                    findings.extend(
                        item for item in model_findings
                        if (item.message, item.line) not in {(f.message, f.line) for f in findings}
                    )
                    scores = score(findings)
                except Exception as exc:
                    model_error = f"Gemini review failed ({type(exc).__name__}). Check the saved key, network, and API availability."

            # Never invent expected behavior from signatures if Gemini did not return tests.
            if model_review and model_review.tests:
                tests = [item.model_dump() for item in model_review.tests]
            else:
                tests = generate_fallback_tests(tree)

            candidate = extract_python_code(model_review.corrected_code) if model_review else ""

            execution = None
            if run_tests and tests and not syntax_error:
                progress.write("Running generated behavior tests in the Docker sandbox…")
                execution = run_cases(candidate or code, tests)

            result = {
                "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                "intent": intent,
                "rationale": rationale,
                "confidence": confidence,
                "retrieve": do_retrieve,
                "retrieval_reason": retrieval_reason,
                "documents": [
                    f"{d.metadata.get('title', 'Guidance')} — {d.metadata.get('source', 'ReviewCrew guide')}"
                    for d in docs
                ],
                "findings": [f.as_dict() for f in findings],
                "scores": scores,
                "syntax_error": syntax_error,
                "llm_review": model_review.summary if model_review else "",
                "fix": candidate,
                "coach": model_review.coaching if model_review else "",
                "tests": tests,
                "execution": execution,
                "rendered_user_prompt": rendered_user_prompt,
            }
            progress.update(label="Review complete", state="complete", expanded=False)

        st.session_state["report"] = result
        st.session_state["code_snapshot"] = code
        st.session_state["model_error"] = model_error
        st.session_state["rag_error"] = rag_error
        st.session_state["lint_error"] = lint_error

    report = st.session_state.get("report")
    if not report:
        st.markdown(
            """<div class="agent"><div class="agent-title">Waiting for your snippet</div><div class="agent-copy">Run a review to see routed intent, grounded findings, scores, tests and coaching here.</div></div>""",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("The starter snippet shows a few intentionally planted issues. Paste your own code or run it as-is.", icon="✳")
    else:
        st.markdown(f"**Route:** `{report['intent']}` · confidence {report['confidence']:.0%}")
        st.caption(report["rationale"])
        st.markdown(
            f"**Retrieval agent:** {'Retrieved ' + str(len(report['documents'])) + ' guidance notes' if report['retrieve'] else 'Skipped retrieval'} — {report['retrieval_reason']}"
        )
        if st.session_state.get("rag_error"):
            st.warning(st.session_state["rag_error"])
        if st.session_state.get("model_error"):
            st.warning(f"Model call failed; deterministic results are shown. {st.session_state['model_error']}")
        elif not report["llm_review"]:
            st.info("Enter a Gemini API key in the sidebar to enable the AI review, suggested correction, and behavior-test generation.")
        if st.session_state.get("lint_error"):
            st.warning(st.session_state["lint_error"])

        m1, m2, m3 = st.columns(3)
        for col, name in zip([m1, m2, m3], ["Overall", "Correctness", "Style"], strict=False):
            col.markdown(
                f'<div class="metric"><div class="metric-label">{name}</div><div class="metric-value">{report["scores"][name]}<span style="font-size:.85rem;color:#8ba0a3"> / 100</span></div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)

        if report["findings"]:
            for item in report["findings"]:
                label = f"{item['severity'].upper()} · {item['category']}" + (f" · line {item['line']}" if item["line"] else "")
                with st.expander(label, expanded=item["severity"] in {"high", "error"}):
                    st.write(item["message"])
                    if item["suggestion"]:
                        st.caption("Suggested direction: " + item["suggestion"])
        else:
            st.success("No issues were found by the deterministic checks.")

        if report["llm_review"]:
            st.markdown("##### Reviewer Agent")
            st.markdown(report["llm_review"])
        if report["coach"]:
            st.markdown("##### Coach Agent")
            st.markdown(report["coach"])
        if report["fix"]:
            with st.expander("Fixer Agent · corrected program", expanded=True):
                st.code(report["fix"], language="python")

        if report["tests"]:
            with st.expander(f"Test Writer Agent · {len(report['tests'])} behavior tests", expanded=True):
                for item in report["tests"]:
                    st.markdown(f"**{item['name']}** · {item.get('purpose', 'Assertion')}")
                    st.code(item["assertion"], language="python")
                if report["execution"]:
                    if report["execution"]["passed"]:
                        st.success("All generated behavior tests passed in the isolated Docker container.")
                    elif report["execution"]["returncode"] is None:
                        st.warning(f"Sandbox unavailable: {report['execution']['stderr']}")
                    else:
                        st.error("Generated behavior tests failed against the proposed corrected program.")
                        if report["execution"]["stderr"]:
                            st.code(report["execution"]["stderr"])
                        if report["execution"]["stdout"]:
                            st.code(report["execution"]["stdout"])
        else:
            st.info("No behavior tests were generated for this review. Test generation requires a successful Gemini review.")

        if report["documents"]:
            with st.expander("Retrieved knowledge sources"):
                for document in report["documents"]:
                    st.markdown(f"- {document}")

        with st.expander("Prompt & Architecture · assignment evidence"):
            st.markdown("**Intent routing rules**")
            st.code("Auto-detect the request locally as debug, style, explain, test, or review. The chosen intent controls retrieval and the review task.", language="text")
            st.markdown("**Multi-role review team system prompt**")
            st.code(TEAM_SYSTEM, language="text")
            st.markdown("**Multi-role review team user prompt template**")
            st.code(TEAM_USER, language="text")
            if report.get("rendered_user_prompt"):
                st.markdown("**Active instantiated user prompt for this run**")
                st.code(report["rendered_user_prompt"], language="text")
            st.markdown("**Structured output instructions supplied to Gemini**")
            st.code(PydanticOutputParser(pydantic_object=TeamReview).get_format_instructions(), language="text")
            st.markdown("**LCEL composition**")
            st.code("ChatPromptTemplate | Gemini ChatOpenAI-compatible model | PydanticOutputParser", language="text")
            st.markdown("**Agent decision**")
            st.json({
                "route": report["intent"],
                "retrieval": report["retrieve"],
                "reason": report["retrieval_reason"],
                "retrieved_titles": report["documents"],
            })

st.markdown("<br><div style='border-top:1px solid #26343a;padding-top:12px;color:#819396;font-size:.78rem'>ReviewCrew · Educational code review · AI output can be wrong — inspect every proposed change.</div>", unsafe_allow_html=True)
