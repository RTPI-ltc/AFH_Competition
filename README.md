# Aurelius Agent

Aurelius Agent is an execution assistant for e-commerce campaign operations. It turns campaign rules, SKU data, knowledge bases, and project conversations into a clear operating workspace for selection, verification, risk review, and final listing decisions.

The product is built for merchants and operations teams who need to move quickly without losing control of pricing rules, inventory constraints, campaign conflicts, or compliance checks.

## What It Does

- Chat with an assistant around the current project and campaign context.
- Maintain projects, tasks, conversation history, and final listing candidates.
- Import official and personal knowledge bases for retrieval-augmented answers.
- Manage a local SKU catalog with price, stock, sales, return rate, certification, and campaign metadata.
- Review product recommendations with checklist items, risks, and human confirmation prompts.
- Configure multiple OpenAI-compatible LLM providers and fail over automatically by priority.
- Keep deterministic fallback behavior available when no model key is configured.

## Product Highlights

### Operations Workspace

Aurelius Agent gives each campaign a working surface for rules, conversations, SKU decisions, and historical summaries. Operators can start a task, ask questions, confirm candidate products, and keep the listing plan visible across the project.

### Knowledge-Backed Chat

The assistant can use official campaign rules and user-uploaded knowledge bases. Uploaded text, documents, spreadsheets, presentations, images, audio, and video metadata are indexed or preserved so the product can support richer retrieval workflows.

### SKU Verification

The SKU catalog stores structured product information including price history, stock, 90-day sales, review rate, return rate, active campaigns, certificates, factories, and lead times. This lets the assistant ground recommendations in operational facts instead of free-form guesses.

### Risk Control

The system checks for absolute marketing claims, price inconsistencies, risky product conditions, missing certificates, campaign conflicts, and high-risk actions. When a decision needs review, the UI surfaces it instead of hiding the uncertainty.

### API Key Failover

The API configuration page supports multiple OpenAI-compatible model configurations. Chat calls try enabled configs in ascending sort order, record status, and automatically continue to the next available config when one fails.

## Tech Stack

- Frontend: React 19, TypeScript, Vite, Tailwind CSS, lucide-react
- Backend: FastAPI, Pydantic, LangGraph
- Storage: SQLite
- LLM: OpenAI-compatible chat completions
- Retrieval: local BM25 and knowledge index snapshots
- Legacy demo UI: Streamlit remains available in `ui/app.py`

## Quick Start

### Backend

```powershell
pip install -r requirements.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend endpoints:

- Health: http://127.0.0.1:8000/api/health
- API docs: http://127.0.0.1:8000/docs

### Frontend

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Open the React app at http://127.0.0.1:5173.

## Model Configuration

You can configure model access in either place:

- In the React app, open `API 配置` and add one or more OpenAI-compatible providers.
- Or create `.env` from `.env.example` and set provider environment variables.

Aliyun DashScope Qwen example:

```text
LLM_PROVIDER=aliyun
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your-api-key
```

If no model is available, deterministic fallback logic keeps the demo usable for local review.

## Core API Surface

The React frontend uses the `/api` prefix:

- `GET /api/projects`
- `POST /api/projects?name=...`
- `POST /api/task/new?project_id=...`
- `GET /api/history?project_id=...`
- `POST /api/chat/stream`
- `GET /api/products`
- `POST /api/products`
- `GET /api/knowledge/official`
- `GET /api/knowledge/personal`
- `POST /api/knowledge/upload`
- `GET /api/llm/configs`
- `POST /api/llm/configs`
- `PUT /api/llm/configs/{config_id}`
- `DELETE /api/llm/configs/{config_id}`

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
agent/       Agent logic, LLM adapter, RAG, risk control, and LangGraph nodes
api/         FastAPI backend and React-compatible API routes
frontend/    React application
sdk/         TypeScript SDK
sql/         SQLite schema
tests/       Backend tests
ui/          Legacy Streamlit UI
data/        Local indexes and ignored runtime data
```

## Notes

- `.env`, local databases, logs, caches, `node_modules`, and frontend build output are ignored.
- Runtime data is stored locally under `data/` by default.
- The product is designed as a runnable local demo for campaign execution assistance, with clear paths to production hardening around authentication, deployment, observability, and managed storage.
