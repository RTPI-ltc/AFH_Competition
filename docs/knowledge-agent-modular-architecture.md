# Knowledge Base Agent Modular Architecture

本文档用于把 MVP 拆成低耦合模块，方便多个 Agent 并发实现。当前产品只保留三个主板块：知识库、Agent 库、API Key 配置；旧商品库能力只作为 legacy 兼容，不进入新 MVP 主路径。

核心取舍：

- Agent 编排从 LangGraph 改为 AgentScope 架构。
- RAG 优先采用 RAG-Anything 的多模态文档 RAG 架构，统一处理文本、图片、表格、公式和复杂版式材料。
- 每个模块只通过 typed schema 交互，避免跨模块直接读写内部文件或数据库表。

## 1. Module Overview

```text
frontend/
  Knowledge Base UI
  Agent Library UI
  API Key Config UI

api/
  routes_knowledge.py
  routes_agents.py
  routes_chat.py
  routes_llm_config.py
  routes_feedback.py

agent/
  runtime/          # AgentScope app/session/service boundary
  agents/           # reusable AgentScope agents
  tools/            # retrieval, review, citation, file tools
  retrieval/        # local/raganything adapters
  ingestion/        # integrated document ingestion pipelines
  evaluation/       # evidence scoring and RAG quality checks
  storage/          # repositories for SQLite/vector/file stores
  schemas/          # shared typed contracts
```

## 2. Open Source Base

| 能力 | MVP 默认 | 可升级开源项目 | 使用边界 |
|---|---|---|---|
| Agent 编排 | AgentScope-oriented runtime facade | AgentScope 2.0 / AgentScope Studio / Agent Service | 多 Agent 路由、消息协作、工具调用、权限边界、运行可观测 |
| RAG 接入 | RAG-Anything facade + local fallback | RAG-Anything built on LightRAG | 文档解析、内容分类、多模态处理、知识图谱索引、跨模态检索 |
| 文档解析 | 当前 text/PDF/docx loader fallback | RAG-Anything MinerU / Docling / PaddleOCR parser | PDF、Office、图片、Markdown、扫描件、复杂版式 |
| 多模态内容处理 | 文本 chunk + metadata | RAG-Anything image/table/equation processors | 图片说明、表格解释、公式解析、跨模态关系保留 |
| 知识索引 | 本地 JSON + BM25 | RAG-Anything multimodal KG + LightRAG storage | graph/vector fusion、层级结构、跨模态实体关系 |
| 混合检索 | BM25 + embedding | RAG-Anything hybrid/local/global/naive query modes | 文本、图像、表格、公式的统一检索和上下文整合 |
| 评估 | pytest 样例 | Ragas / AgentScope eval ecosystem | faithfulness、context precision、retrieval regression |
| 后端 API | FastAPI | FastAPI | 保持现有服务入口，避免框架级迁移 |
| 前端 | React + Vite | React + Vite | 保持现有三大板块 |

参考依据：

- AgentScope 2.0 官方定位为生产可用的 Agent framework，提供 ReAct agent、tools、skills、human-in-the-loop、memory、planning、evaluation、MCP/A2A、message hub 和 Agent Service。
- RAG-Anything 官方定位为 all-in-one multimodal document processing RAG system，基于 LightRAG，支持文本、图片、表格、公式和混合内容文档的一体化处理与查询。
- RAG-Anything 官方架构包含 Document Parsing、Content Analysis、Knowledge Graph、Intelligent Retrieval 四段，并提供 MinerU、Docling、PaddleOCR 等 parser 选择。
- RAG-Anything 支持 `raganything` PyPI 安装，`raganything[all]` 可启用更多格式能力；Office 文档处理需要单独安装 LibreOffice。
- RAG-Anything 当前 release 较新，MVP 应通过 adapter/facade 接入，并保留当前本地 RAG fallback，避免 demo 被重型解析依赖阻塞。
- 依赖落地建议：先把 `raganything` 做成 optional extra 或延迟导入；等 ingestion adapter 可跑通后，再决定是否把 `raganything[all]` 写入默认 `requirements.txt`。

## 3. Core Schemas

所有模块只通过 typed schema 传递数据，不直接依赖对方内部实现。

```python
KnowledgeSource:
  id: str
  name: str
  type: official | personal
  description: str
  file_count: int
  chunk_count: int
  rag_backend: str
  index_backend: str

DocumentChunk:
  id: str
  knowledge_id: str
  text: str
  content_type: text | image | table | equation | generic
  source_file: str
  page: int | None
  section: str | None
  char_start: int | None
  char_end: int | None
  asset_path: str | None
  related_chunk_ids: list[str]
  metadata: dict

RetrievalHit:
  chunk: DocumentChunk
  dense_score: float | None
  sparse_score: float | None
  rerank_score: float | None
  fused_score: float
  hit_kind: dense | sparse | graph | hybrid | multimodal | external
  modality: text | image | table | equation | mixed

AgentSpec:
  id: str
  name: str
  scenario: str
  system_prompt: str
  tool_names: list[str]
  output_schema: str

AgentRun:
  id: str
  agent_id: str
  project_id: str
  conversation_id: str
  input: str
  selected_knowledge_ids: list[str]
  status: running | completed | failed | needs_human

AgentOutput:
  reply: str
  evidence: list[RetrievalHit]
  confidence: high | medium | low
  evidence_notes: list[str]
  follow_up_questions: list[str]
  retrieval_error: str | None
```

## 4. Module Boundaries

### A. AgentScope Runtime

目录建议：`agent/runtime/`

职责：

- 封装 AgentScope 初始化、session、message hub、tool registry 和 Agent Service 边界。
- 暴露一个稳定的 `run_agent()` 给 API 层调用。
- 负责多 Agent 协作、人工确认入口、超时和失败恢复。

不负责：

- 不解析文件。
- 不直接实现检索。
- 不写 UI 状态。

建议接口：

```python
def build_runtime(config: RuntimeConfig) -> AgentRuntime: ...
def run_agent(request: AgentRunRequest) -> AgentRunResult: ...
def register_tools(runtime: AgentRuntime, tools: list[ToolSpec]) -> None: ...
```

AgentScope 对应关系：

```text
AgentScope App/Runtime
  -> session and message routing
  -> AgentService boundary
  -> tool permission boundary
  -> observability events
```

适合分配给 Agent 1。

### B. Agent Library

目录建议：`agent/agents/`

职责：

- 定义可复用场景 Agent。
- 每个 Agent 有独立 system prompt、工具列表、输出 schema、评估规则。
- 每个 Agent 文件只暴露 `spec()` 和 `build_agent()`。

首批 Agent：

```text
hackathon_agent.py
course_tutor_agent.py
project_application_agent.py
enterprise_knowledge_agent.py
evidence_review_agent.py
```

建议接口：

```python
def spec() -> AgentSpec: ...
def build_agent(runtime: AgentRuntime) -> Any: ...
```

适合分配给 Agent 2。

### C. Multimodal RAG Ingestion

目录建议：`agent/ingestion/`

职责：

- 接收上传文件、URL 或纯文本。
- 调用 RAG-Anything 的 document parsing 和 content analysis。
- 自动拆解 text/image/table/equation/generic content。
- 保留页码、章节、图片/表格/公式资产路径、跨模态上下文关系。
- 输出 `DocumentChunk[]` 兼容层，或交给 RAG-Anything/LightRAG 工作目录直接索引。

推荐 MVP 路线：

```text
Uploaded files / text
  -> raganything_adapter.py
  -> RAGAnythingConfig(parser="mineru", parse_method="auto")
  -> process_document_complete()
  -> multimodal content list
  -> LightRAG-backed graph/vector index
  -> normalized DocumentChunk compatibility view
```

轻量 fallback 路线：

```text
Uploaded text / simple docs
  -> existing local parser
  -> text-only chunks
  -> local BM25 + embedding index
```

建议接口：

```python
def ingest_source(source: RawSource, options: IngestionOptions) -> IngestionResult: ...
def preview_chunks(source: RawSource, options: IngestionOptions) -> list[DocumentChunk]: ...
def sync_to_index(result: IngestionResult) -> IndexResult: ...
def list_multimodal_assets(knowledge_id: str) -> list[KnowledgeAsset]: ...
```

适合分配给 Agent 3。

### D. Multimodal Retrieval Engine

目录建议：`agent/retrieval/`

职责：

- 建立索引。
- 执行 text / graph / multimodal / hybrid retrieval。
- 做 RRF 或 rerank。
- 返回 `RetrievalHit[]`。

不负责：

- 不生成最终回答。
- 不判断业务任务完成度。

建议拆分：

```text
retrieval/
  base.py
  local_hybrid_adapter.py
  raganything_adapter.py
  multimodal_context.py
  reranker.py
```

建议接口：

```python
def build_index(knowledge_id: str, chunks: list[DocumentChunk]) -> IndexResult: ...
def retrieve(query: str, knowledge_ids: list[str], top_k: int) -> list[RetrievalHit]: ...
def retrieve_multimodal(query: MultimodalQuery) -> list[RetrievalHit]: ...
```

适合分配给 Agent 4。

### E. Trust And Evaluation

目录建议：`agent/evaluation/`

职责：

- 检查回答是否有证据支撑。
- 标记低置信、未命中、冲突材料、需要人工复核项。
- 为后续 Ragas 或 AgentScope evaluation 接入保留接口。

建议接口：

```python
def score_evidence(answer: str, hits: list[RetrievalHit]) -> EvidenceScore: ...
def detect_conflicts(hits: list[RetrievalHit]) -> list[Conflict]: ...
def build_review_flags(output: AgentOutput) -> list[ReviewFlag]: ...
```

适合分配给 Agent 5。

### F. Storage Layer

目录建议：`agent/storage/`

职责：

- 封装 SQLite、RAG-Anything working_dir、LightRAG storage、本地文件索引路径。
- 给 API 和 Agent 层提供 repository。
- 避免业务代码到处直接写 SQL 或文件路径。

建议拆分：

```text
knowledge_repo.py
conversation_repo.py
agent_run_repo.py
feedback_repo.py
vector_store_repo.py
raganything_repo.py
```

适合分配给 Agent 6。

### G. API Layer

目录建议：`api/`

建议从当前 `api/frontend.py` 逐步拆成：

```text
routes_knowledge.py
routes_agents.py
routes_chat.py
routes_llm_config.py
routes_feedback.py
```

职责：

- 只做 request/response validation。
- 调 service/runtime/repository。
- 不包含检索、提示词、业务判断。

适合分配给 Agent 7。

### H. Frontend

目录建议：

```text
frontend/src/pages/
  KnowledgePage.tsx
  AgentLibraryPage.tsx
  ApiConfigPage.tsx
  ChatPage.tsx
  FeedbackDashboardPage.tsx
```

当前三个主板块：

- Knowledge Base
- Agent Library
- API Key Config

下一步可加第四个非主入口：Feedback Dashboard，用于运营看板。

适合分配给 Agent 8。

## 5. Parallel Work Packages

| 并发任务 | 负责目录 | 交付物 | 依赖 |
|---|---|---|---|
| Shared Schemas | `agent/schemas` | KnowledgeSource、DocumentChunk、RetrievalHit、AgentSpec、AgentOutput | 无 |
| AgentScope Runtime | `agent/runtime` | runtime facade、tool registry、run_agent 接口 | schemas |
| Agent Library | `agent/agents` | 5 个 AgentSpec + build_agent | schemas, runtime |
| RAG-Anything Ingestion | `agent/ingestion` | RAG-Anything adapter + multimodal chunk preview | schemas |
| Retrieval Adapter | `agent/retrieval` | local adapter + raganything adapter 接口 | schemas, ingestion |
| Trust/Eval | `agent/evaluation` | evidence score + low-confidence flags | schemas, retrieval |
| API Split | `api/routes_*` | REST/SSE routes | runtime, repos |
| Frontend Panels | `frontend/src` | 三主板块页面和 API client | API contract |
| Tests & Demo Data | `tests`, `data/samples` | sample AIRS/course KB, e2e tests | API stable 后 |

并发执行规则：

- 所有 Agent 先只改自己负责目录。
- 共享 schema 先落地，其它 Agent import，不重复定义。
- API contract 变更必须先写在 `docs/api-contract.md`。
- 每个模块至少有一个不依赖真实 LLM API 的单元测试。
- RAG 测试必须覆盖：命中、有证据低置信、无命中、冲突资料。

## 6. Landing Order

1. 建 `agent/schemas/`，统一 KnowledgeSource、DocumentChunk、RetrievalHit、AgentSpec、AgentOutput。
2. 建 `agent/runtime/`，先实现 AgentScope facade；如果 AgentScope 未安装，用 deterministic local runtime fallback 保持 demo 可跑。
3. 把 `agent/chat.py` 的 prompt、normalization 和 tool 调用迁到 `agent/runtime/`。
4. 建 `agent/agents/`，先实现 hackathon/course 两个 AgentSpec。
5. 建 `agent/ingestion/raganything_pipeline.py`，用 RAG-Anything 做文档解析、内容分类、多模态资产抽取和索引；保留当前 local RAG fallback。
6. 把现有 `agent/rag/*` 包一层 `agent/retrieval/local_hybrid_adapter.py`。
7. 建 `agent/retrieval/raganything_adapter.py`，把 RAG-Anything 查询结果归一化为 `RetrievalHit[]`。
8. 拆 `api/frontend.py`，保留兼容路由，但新前端只调 `routes_*`。
9. 前端页面目录化，Agent 库改读 `/api/agents`，不写死卡片。
10. 接入 Ragas/AgentScope evaluation，形成运营看板指标。

## 7. Current Repository Assets To Keep

- `frontend` 三板块页面结构。
- `agent/rag/*` 的 BM25 + dense fallback。
- `api/llm/configs` 的 API Key 配置。
- SQLite 项目、对话、知识库表。
- 现有 RAG 和 LLM config 测试。

## 8. Current Repository Assets To Retire Gradually

- 旧电商商品库表和相关兼容 API。
- `agent/nodes/product_verifier.py` 等旧商品核查节点。
- Legacy Streamlit 规则解析 UI。
- `agent/graph.py` 的 LangGraph graph 构建路径。

这些不必一次性删除。先从新 API、新 runtime 和新前端隔离，等 MVP 稳定后再做 schema migration 和 legacy cleanup。
