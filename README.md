# ReviewCrew

ReviewCrew is a multi-agent code review and debugging app built for Assignment 1's **Code Review & Debug Squad** option. It accepts Python snippets, routes debugging, style, explanation, and testing requests, and combines deterministic analysis with Gemini feedback grounded in a Chroma knowledge base.

## What it demonstrates

- **Bug Finder**: Python AST and Gemini checks look for correctness, security, boundary, and runtime risks.
- **Style/Lint Reviewer**: Ruff checks common Python errors, conventions, imports, and naming.
- **Fixer**: returns a complete corrected program grounded in findings and retrieved guidance.
- **Test Writer**: generates behavior assertions for the corrected program and can execute them in Docker.
- **Intent router**: routes debugging, style, explanation, or test requests.
- **Agentic RAG**: the intent route controls whether Chroma retrieval runs; Python guidance and debugging examples with source references are included in the review prompt.
- **LangChain + LCEL**: `ChatPromptTemplate | model | PydanticOutputParser` connects the prompt, Gemini, and structured review output.
- **ChromaDB**: persists coding guidance and retrieves by similarity; local Hugging Face embeddings are used by default.

The deterministic AST and Ruff checks remain available without a key. Enter a Gemini API key to enable the coordinated Bug Finder, Style/Lint Reviewer, Fixer, Coach, and Test Writer output. The review team answers in one structured model request to reduce waiting. Prompt templates and routing decisions are visible in **Prompt & Architecture**.

## Start

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On first use, Chroma may download the configured embedding model (`sentence-transformers/all-MiniLM-L6-v2`) if it is not cached. The model and Chroma store are cached for the life of the Streamlit process to avoid reloading them on every review. Set `HF_HOME` to a writable cache directory if needed.

### Gemini API key

Paste your Gemini API key into the sidebar. The app uses Google's OpenAI-compatible Gemini endpoint and the `gemini-3.8-flash` model automatically, so no model name or endpoint setup is needed. The key is saved in the computer's credential manager and reused the next time the app opens.

Your code and prompts are sent to Google's Gemini API when the review runs; do not submit secrets or proprietary code unless approved for that service.

## Isolated test execution

Install and start Docker Desktop, then download the small Python sandbox image once:

```bash
docker pull python:3.12-alpine
```

The **Run generated assertions in Docker** option is on by default. It runs the model's behavior assertions against the proposed corrected program in a disposable container with no network, a read-only root filesystem, dropped Linux capabilities, process/memory/CPU limits, and no host files mounted. If Docker or the image is unavailable, the report explains how to enable the sandbox; the app never falls back to unsandboxed execution. Docker containers provide process isolation but are not a substitute for a dedicated VM when handling highly hostile code.

## Knowledge base

The initial knowledge base contains concise Python review guidance and debugging examples, with relevant Python documentation and PEP references in Chroma metadata. Chroma persists it under `.reviewcrew/chroma/`. Add or revise guidance in `reviewcrew/knowledge.py`; the app synchronizes the documents on launch. No user code is uploaded to Chroma.

## Project layout

```text
app.py                 Streamlit interface and routed workflow
reviewcrew/            Review team, analyzers, retrieval, model and sandbox runner
.streamlit/            Streamlit theme and configuration
```

## Assignment mapping

| Acceptance criterion | Implementation |
|---|---|
| LLM integration | Gemini API through Google's OpenAI-compatible endpoint |
| Interactive GUI | Streamlit workspace with code editor, request routing and reports |
| Prompt engineering | Role-based zero-shot prompt, output schema, reflection/self-check; all active system and user prompts displayed in UI |
| LangChain + LCEL | LangChain prompt templates composed with model and output parser |
| Agentic RAG | Intent-dependent Chroma retrieval before the review team call, with source metadata |
| Intent detection/routing | Local intent classifier plus explicit route selector and retrieval policy |
| Vector DB | Persistent Chroma collection with local sentence-transformer embeddings |

## Scope and limitations

The review roles are orchestrated in one structured model response to reduce latency. Static checks and Ruff findings are deterministic; model findings and generated tests can still be wrong. Review proposed changes and test expectations. The Docker runner is an educational sandbox, not a hardened service for untrusted public traffic.

This is an educational reviewer, not a formal security audit. Static checks are intentionally conservative and may miss defects or flag code that is safe in context. Generated tests can be wrong, and the Docker sandbox is not a hardened multi-tenant service. Review changes and test expectations before adopting them.
