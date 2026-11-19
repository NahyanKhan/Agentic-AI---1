# ReviewCrew

ReviewCrew is a multi-agent code review and debugging app built for Assignment 1's **Code Review & Debug Squad** option. It accepts Python snippets, routes debugging, style, explanation, and testing requests, and combines deterministic analysis with Gemini feedback grounded in a Chroma knowledge base.

## What it demonstrates

- **Bug Finder**: Python AST checks for common correctness risks and suspicious constructs.
- **Style Reviewer**: naming, structure, and readability checks.
- **Fixer**: proposes a patch using retrieved guidance and findings.
- **Test Writer**: generates safe, deterministic input cases from function signatures and can run them with an explicit opt-in.
- **Intent router**: routes debugging, style, explanation, or test requests.
- **Agentic RAG**: the route selects whether coding guidance is retrieved; results are included in grounded LLM prompts.
- **LangChain + LCEL**: `ChatPromptTemplate | model | StrOutputParser` is used for model calls.
- **ChromaDB**: persists coding guidance and retrieves by similarity; local Hugging Face embeddings are used by default.

The reviewer remains useful without an API key: deterministic agents still produce findings and tests. Gemini features become active when a Gemini API key is entered. Prompt templates and routing decisions are visible in the app's **Prompt & Architecture** panel.

## Start

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On first launch, Chroma downloads the configured embedding model (`sentence-transformers/all-MiniLM-L6-v2`) if it is not cached. Set `HF_HOME` to a writable cache directory if needed.

### Gemini API key

Paste your Gemini API key into the sidebar. The app uses Google's OpenAI-compatible Gemini endpoint and the `gemini-3.8-flash` model automatically, so no model name or endpoint setup is needed. The key is saved in the computer's credential manager and reused the next time the app opens.

Your code and prompts are sent to Google's Gemini API when the review runs; do not submit secrets or proprietary code unless approved for that service.

## Code execution safety

Test execution is **off by default**. If enabled, the app starts the submitted Python code in a temporary working directory with a short timeout and stripped environment. This is a convenience guard, **not an OS security sandbox**: arbitrary code can still access resources available to the app's operating-system account. Only enable execution for code you trust, and run the app locally. For shared or public deployments, disable execution or place it behind a real container/VM sandbox with network and filesystem restrictions.

## Knowledge base

The initial knowledge base contains concise Python review guidance authored for the demo. Chroma persists it under `.reviewcrew/chroma/`. Add or revise guidance in `reviewcrew/knowledge.py`; the app synchronizes the documents on launch. No external code corpus is uploaded.

## Project layout

```text
app.py                 Streamlit interface and routed workflow
reviewcrew/            Agents, analyzers, retrieval, model and runner
prompts/               Human-readable prompt templates
.streamlit/            Streamlit theme and configuration
```

## Assignment mapping

| Acceptance criterion | Implementation |
|---|---|
| LLM integration | Gemini API through Google's OpenAI-compatible endpoint |
| Interactive GUI | Streamlit workspace with code editor, request routing and reports |
| Prompt engineering | Zero-shot role prompts, structured review steps, reflection pass; displayed in UI |
| LangChain + LCEL | LangChain prompt templates composed with model and output parser |
| Agentic RAG | Intent-dependent retrieval before reviewer/coach model calls |
| Intent detection/routing | Rule-based route confidence with explicit selector override |
| Vector DB | Chroma persistent collection with local sentence-transformer embeddings |

## Limitations

This is an educational reviewer, not a formal security audit. Static checks are intentionally conservative and may miss defects or flag code that is safe in context. LLM feedback may be incorrect. Review changes before adopting them.
