# ReviewCrew

ReviewCrew is an educational multi-agent code review and debugging app built for the **Code Review & Debug Squad** assignment. It accepts Python snippets, routes debugging, style, explanation, and testing requests, and combines deterministic analysis with Gemini feedback grounded in a Chroma knowledge base.

## What it demonstrates

- **Bug Finder**: Python AST and Gemini checks look for correctness, security, boundary, and runtime risks.
- **Style/Lint Reviewer**: Ruff checks common Python errors, conventions (PEP 8), imports, and naming.
- **Fixer**: returns a complete corrected program grounded in static findings and retrieved guidance.
- **Test Writer**: generates behavior assertions for the corrected program and can execute them in an isolated Docker container.
- **Intent router**: routes debugging, style, explanation, or test requests.
- **Agentic RAG**: the intent route controls whether Chroma retrieval runs; Python guidance and debugging examples with source references are included in the review prompt.
- **LangChain + LCEL**: `ChatPromptTemplate | model | PydanticOutputParser` connects the prompt, Gemini, and structured review output.
- **ChromaDB**: persists coding guidance and retrieves by similarity; local Hugging Face embeddings are used by default.

The deterministic AST and Ruff checks remain available without an API key. Enter a Gemini API key in the sidebar to enable the coordinated Bug Finder, Style/Lint Reviewer, Fixer, Coach, and Test Writer output. The review team answers in one structured model request to avoid latency from sequential calls. Prompt templates and routing decisions are visible in **Prompt & Architecture**.

## Start

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On first launch, Chroma may download the configured embedding model (`sentence-transformers/all-MiniLM-L6-v2`) if it is not cached. The model and Chroma store are cached for the life of the Streamlit process using `@st.cache_resource` to avoid reloading them on every review.

### Gemini API key

Enter your Gemini API key in the sidebar. The app uses Google's OpenAI-compatible Gemini endpoint (`gemini-2.5-flash` with automatic fallback to `gemini-1.5-flash`), so no endpoint setup is needed. The key is saved securely in your computer's credential manager (via `keyring`) and reused on future launches. It is never logged, printed, or written to Git repository files.

## Isolated test execution

To run generated tests in the isolated sandbox, install and start Docker Desktop, then download the lightweight sandbox image:

```bash
docker pull python:3.12-alpine
```

The **Run generated assertions in Docker** option is enabled by default. It executes the generated behavior assertions against the proposed corrected program inside a disposable container with:
- No network access (`--network=none`)
- Read-only root filesystem (`--read-only`)
- Dropped Linux capabilities (`--cap-drop=ALL`)
- Prevented privilege escalation (`--security-opt=no-new-privileges`)
- Strict CPU and memory limits (`--cpus=0.5`, `--memory=192m`, `--pids-limit=64`)
- Unprivileged nobody user (`--user=65534:65534`)
- No host filesystem mounts

If Docker is not running or the image is missing, the app reports clear diagnostic guidance and does not run untrusted code directly on the host.

## Knowledge base

The knowledge base contains curated Python review guidance and debugging examples, with official Python documentation and PEP references in Chroma metadata. Chroma persists it under `.reviewcrew/chroma/`. Guidance can be customized in `reviewcrew/knowledge.py`; documents are synchronized on launch. No user code is uploaded to Chroma.

## Project layout

```text
app.py                 Streamlit interface and routed workflow
reviewcrew/            Review team, analyzers, retrieval, model and sandbox runner
.streamlit/            Streamlit theme and configuration
```

## Assignment mapping

| Acceptance criterion | Implementation |
|---|---|
| LLM integration | Gemini API through Google's OpenAI-compatible endpoint (`gemini-2.5-flash` / `gemini-1.5-flash`) |
| Interactive GUI | Streamlit workspace with code editor, request routing, live progress, and reports |
| Prompt engineering | Role-based zero-shot prompt, structured schema, reflection/self-check; system and active prompts displayed in UI |
| LangChain + LCEL | LangChain prompt templates composed with model and PydanticOutputParser (`ChatPromptTemplate \| model \| PydanticOutputParser`) |
| Agentic RAG | Intent-dependent Chroma retrieval before the review squad call, passing text and source metadata |
| Intent detection/routing | Local intent classifier plus explicit route selector and retrieval policy |
| Vector DB | Persistent Chroma collection with local sentence-transformer embeddings cached across runs |

## Scope and limitations

The review roles are orchestrated in one structured model response to reduce latency. Static checks and Ruff findings are deterministic; model findings and generated tests should always be inspected. The Docker runner is a sandboxed container for local evaluation, not a multi-tenant cloud sandbox.
