from __future__ import annotations

import json
from datetime import datetime

import streamlit as st
import keyring
from langchain_core.prompts import ChatPromptTemplate

from reviewcrew.analyzer import analyze, function_names, score
from reviewcrew.models import lcel, make_model
from reviewcrew.prompts import (COACH_SYSTEM, COACH_USER, FIX_SYSTEM, FIX_USER,
                                REVIEW_SYSTEM, REVIEW_USER, ROUTER_SYSTEM, ROUTE_USER)
from reviewcrew.retrieval import open_store, retrieve
from reviewcrew.routing import detect_intent, should_retrieve
from reviewcrew.routing import detect_intent_with_model
from reviewcrew.runner import run_cases

GEMINI_KEYRING_SERVICE = "ReviewCrew"
GEMINI_KEYRING_ACCOUNT = "gemini-api-key"
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


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

st.set_page_config(page_title="ReviewCrew · Agentic Code Review", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

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
        help="Saved securely in this computer's credential manager for future launches.",
        key="gemini_api_key",
    ).strip()
    key_save_failed = bool(api_key and api_key != saved_api_key and not save_api_key(api_key))
    if key_save_failed:
        st.warning("The key works for this session, but this computer could not save it securely for next time.")
    st.divider()
    st.markdown("**Review route**")
    route_choice = st.selectbox("Choose an intent", ["Auto-detect", "Full review", "Debug", "Style review", "Explain", "Generate tests"], label_visibility="collapsed")
    run_tests = st.checkbox("Run generated assertions", value=False, help="Runs submitted Python in a temporary subprocess with a short timeout. This is not a security sandbox; only use code you trust.")
    st.caption("Execution stays off until you opt in.")
    st.divider()
    st.caption("Local corpus · ChromaDB · LCEL")

AGENTS = [
    ("01 · Bug Finder", "AST checks catch common correctness, safety and edge-case risks."),
    ("02 · Style Reviewer", "Naming, readability and maintainability signals."),
    ("03 · Fixer", "Minimal patch suggestions that preserve the apparent API."),
    ("04 · Test Writer", "Deterministic assertion ideas, with optional opt-in run."),
]
cols = st.columns(4)
for col, (title, copy) in zip(cols, AGENTS):
    col.markdown(f'<div class="agent"><div class="agent-title">{title}</div><div class="agent-copy">{copy}</div></div>', unsafe_allow_html=True)

left, right = st.columns([1.12, .88], gap="large")
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
    code = st.text_area("Python source", value=sample, height=350, label_visibility="collapsed", help="Paste a Python snippet. Avoid secrets and proprietary code when using a remote API.")
    request = st.text_input("What should the team focus on?", value="Review this code and suggest fixes for bugs and safety risks.", placeholder="e.g. Find edge cases and explain how to fix them")
    run = st.button("Run agent review  →", type="primary", use_container_width=True)
    st.caption("Python only · Findings combine deterministic checks with optional model reasoning")

with right:
    st.markdown("#### Review report")
    if run:
        intents = {"Full review": "review", "Debug": "debug", "Style review": "style", "Explain": "explain", "Generate tests": "test"}
        model = None
        model_error = None
        if api_key:
            try:
                model = make_model("Gemini", GEMINI_MODEL, api_key, GEMINI_BASE_URL)
            except Exception as exc:
                model_error = f"Could not initialize the Gemini model ({type(exc).__name__})."
        if route_choice == "Auto-detect":
            intent, rationale, confidence = detect_intent(request)
            if model:
                try:
                    intent, rationale, confidence = detect_intent_with_model(request, model)
                except Exception as exc:
                model_error = f"Gemini router call failed ({type(exc).__name__}); used the built-in route instead."
        else:
            intent, rationale, confidence = intents[route_choice], "Intent selected explicitly in the sidebar.", 1.0
        do_retrieve, retrieval_reason = should_retrieve(intent, request)
        findings, tree, syntax_error = analyze(code)
        scores = score(findings)
        store, rag_error, docs = None, None, []
        if do_retrieve:
            try:
                store = open_store()
                docs = retrieve(store, f"{intent}: {request}\n{code}", k=4)
            except Exception as exc:
                rag_error = f"Chroma retrieval unavailable: {exc}"
        context = "\n".join(f"- {d.page_content}" for d in docs) or "No retrieved guidance available."
        result = {"time": datetime.now().astimezone().isoformat(timespec="seconds"), "intent": intent, "rationale": rationale, "confidence": confidence, "retrieve": do_retrieve, "retrieval_reason": retrieval_reason, "documents": [d.metadata.get("title", "Guidance") for d in docs], "findings": [f.as_dict() for f in findings], "scores": scores, "syntax_error": syntax_error, "llm_review": "", "fix": "", "coach": "", "tests": [], "execution": None}

        if model and not syntax_error:
            try:
                result["llm_review"] = lcel(ChatPromptTemplate.from_messages([("system", REVIEW_SYSTEM), ("human", REVIEW_USER)]), model, intent=intent, request=request, context=context, findings=json.dumps(result["findings"], ensure_ascii=False), code=code)
                result["coach"] = lcel(ChatPromptTemplate.from_messages([("system", COACH_SYSTEM), ("human", COACH_USER)]), model, intent=intent, scores=json.dumps(scores), findings=json.dumps(result["findings"], ensure_ascii=False), context=context, code=code)
                if intent in {"debug", "review"} and findings:
                    result["fix"] = lcel(ChatPromptTemplate.from_messages([("system", FIX_SYSTEM), ("human", FIX_USER)]), model, findings=json.dumps(result["findings"], ensure_ascii=False), context=context, code=code)
            except Exception as exc:
                model_error = f"Gemini request failed ({type(exc).__name__}). Check that the API key is valid and Gemini API access is enabled for it."

        if intent == "test" or route_choice == "Generate tests":
            names = function_names(tree)
            result["tests"] = [{"name": n, "assertion": f"assert callable({n!r})"} for n in names]
            if names:
                result["tests"] = [{"name": n, "assertion": f"assert callable({n})"} for n in names]
            if not names:
                result["tests"] = [{"name": "syntax", "assertion": "assert True  # Add function-specific examples for this snippet"}]
        elif function_names(tree):
            result["tests"] = [{"name": n, "assertion": f"assert callable({n})"} for n in function_names(tree)]
        if run_tests and result["tests"] and not syntax_error:
            result["execution"] = run_cases(code, result["tests"])
        st.session_state["report"] = result
        st.session_state["code_snapshot"] = code
        st.session_state["model_error"] = model_error
        st.session_state["rag_error"] = rag_error

    report = st.session_state.get("report")
    if not report:
        st.markdown("""<div class="agent"><div class="agent-title">Waiting for your snippet</div><div class="agent-copy">Run a review to see routed intent, grounded findings, scores, tests and coaching here.</div></div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("The starter snippet shows a few intentionally planted issues. Paste your own code or run it as-is.", icon="✳")
    else:
        st.markdown(f"**Route:** `{report['intent']}` · confidence {report['confidence']:.0%}")
        st.caption(report["rationale"])
        st.markdown(f"**Retrieval agent:** {'Retrieved ' + str(len(report['documents'])) + ' guidance notes' if report['retrieve'] else 'Skipped retrieval'} — {report['retrieval_reason']}")
        if st.session_state.get("rag_error"):
            st.warning(st.session_state["rag_error"])
        if st.session_state.get("model_error"):
            st.warning(f"Model call failed; deterministic results are shown. {st.session_state['model_error']}")
        m1, m2, m3 = st.columns(3)
        for col, name in zip([m1, m2, m3], ["Overall", "Correctness", "Style"]):
            col.markdown(f'<div class="metric"><div class="metric-label">{name}</div><div class="metric-value">{report["scores"][name]}<span style="font-size:.85rem;color:#8ba0a3"> / 100</span></div></div>', unsafe_allow_html=True)
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
            with st.expander("Fixer Agent · suggested patch"):
                st.markdown(report["fix"])
        if report["tests"]:
            with st.expander(f"Test Writer Agent · {len(report['tests'])} checks", expanded=True):
                for item in report["tests"]:
                    st.code(item["assertion"], language="python")
                if report["execution"]:
                    if report["execution"]["passed"]:
                        st.success("Generated assertions passed.")
                    else:
                        st.error("Generated assertions failed or timed out.")
                        if report["execution"]["stderr"]:
                            st.code(report["execution"]["stderr"])
        if report["documents"]:
            with st.expander("Retrieved knowledge sources"):
                for title in report["documents"]:
                    st.markdown(f"- {title} · ReviewCrew Python review guide")
        with st.expander("Prompt & Architecture · assignment evidence"):
            st.markdown("**Intent router system prompt**")
            st.code(ROUTER_SYSTEM, language="text")
            st.markdown("**Reviewer system prompt**")
            st.code(REVIEW_SYSTEM, language="text")
            st.markdown("**Reviewer user prompt template**")
            st.code(REVIEW_USER, language="text")
            st.markdown("**LCEL composition**")
            st.code("ChatPromptTemplate.from_messages([...]) | chat_model | StrOutputParser()", language="python")
            st.markdown("**Agent decision**")
            st.json({"route": report["intent"], "retrieval": report["retrieve"], "reason": report["retrieval_reason"], "retrieved_titles": report["documents"]})

st.markdown("<br><div style='border-top:1px solid #26343a;padding-top:12px;color:#819396;font-size:.78rem'>ReviewCrew · Educational code review · AI output can be wrong — inspect every proposed change.</div>", unsafe_allow_html=True)
