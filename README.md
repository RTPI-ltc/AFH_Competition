# Knowledge Base Agent

Knowledge Base Agent is a runnable MVP for a trustworthy, task-oriented knowledge service platform. It turns scattered documents, course materials, event rules, and project files into searchable knowledge bases with cited answers, review prompts, and reusable Agent workflows.

The current product keeps three primary modules:

- Knowledge Base: upload text and files, build local RAG indexes, select sources for retrieval.
- Agent Library: start scenario agents for hackathon support, course tutoring, project application checks, enterprise knowledge, and evidence review.
- API Configuration: manage OpenAI-compatible model providers and fail over by priority.

## MVP Focus

The MVP is designed around two landing scenarios:

- AIRS hackathon knowledge assistant: rules Q&A, task background explanation, submission material checks, judging criteria explanation, FAQ reuse, and organizer-side question analysis.
- General course AI teaching assistant: course Q&A, concept explanation, practice question generation, revision guidance, out-of-scope warnings, and teacher-side weak-point analysis.

## Core Flow

```text
Upload sources -> multimodal parse -> RAG-Anything retrieval -> Agent answer/task output -> citations -> low-confidence or human-review prompts
```

## Tech Stack

- Frontend: React 19, TypeScript, Vite, Tailwind CSS, lucide-react
- Backend: FastAPI, Pydantic, AgentScope-oriented Agent runtime
- Storage: SQLite
- Retrieval: RAG-Anything-oriented multimodal RAG with local BM25/embedding fallback
- LLM: OpenAI-compatible chat completions

## Quick Start

Backend:

```powershell
pip install -r requirements.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Open the React app at http://127.0.0.1:5173.

## Retrieval Mode

The architecture targets RAG-Anything for multimodal document parsing and retrieval. The local demo always keeps a BM25 text index, so the MVP can answer with local retrieval even when the GPU host is unavailable.

GPU routing is controlled by `AFH_GPU_MODE`:

```text
AFH_GPU_MODE=auto      # prefer GPU semantic embedding, fall back to local BM25
AFH_GPU_MODE=off       # never call GPU; build/query BM25-only local indexes
AFH_GPU_MODE=required  # fail loudly if GPU semantic embedding is unavailable
```

Useful defaults for local MVP work:

```text
AFH_GPU_MODE=auto
AFH_ALLOW_HASH_RAG_FALLBACK=0
AFH_RAG_PRELOAD=0
```

By default the app will not download embedding models inside a live chat request. That avoids a long first-response delay if HuggingFace is slow or blocked. To explicitly allow a one-time local model download, set:

```text
AFH_RAG_ALLOW_MODEL_DOWNLOAD=1
```

For a no-sudo GPU host, run the user-space embedding worker on the remote machine and point the local RAG stack to it:

```bash
bash scripts/start_gpu_embedding_worker.sh
```

```text
AFH_RAG_EMBEDDING_URL=http://127.0.0.1:8010/embed
AFH_RAG_EMBEDDING_TIMEOUT=8
AFH_GPU_CIRCUIT_BREAKER_SECONDS=60
AFH_ALLOW_HASH_RAG_FALLBACK=0
```

When the worker is on another host, use an SSH tunnel or a private network route rather than exposing the worker publicly. If the worker cannot be reached in `auto` mode, the circuit breaker opens briefly and retrieval falls back to local BM25; `required` mode is the only mode that treats this as a hard failure.

Runtime status is available at:

```text
GET /api/runtime/status
```

Rebuild indexes after changing embedding backend:

```powershell
python scripts/build_rag_index.py --rebuild-all
```

## Validation

Run backend tests:

```powershell
pytest tests\ -v
```

Build the frontend:

```powershell
cd frontend
npm run build
```

## Repository Layout

```text
agent/       Agent logic, LLM adapter, RAG, and AgentScope-oriented runtime
api/         FastAPI backend and React-compatible API routes
frontend/    React application
sdk/         TypeScript SDK
sql/         SQLite schema
tests/       Backend tests
ui/          Legacy Streamlit UI
data/        Local indexes and ignored runtime data
```
