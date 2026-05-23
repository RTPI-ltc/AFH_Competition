# AFH_Competition — 知识库 RAG 系统实施方案

## Context（为什么做这个）

现状：项目已有「个人知识库」前端 UI（`frontend/src/components/Knowledge/`），但后端只用内存字典 `_personal_knowledge`（[api/frontend.py:16](AFH_Competition-main/api/frontend.py#L16)）保存上传文本，**重启即丢**。而且 chat 接口虽然接收 `knowledge_ids` 参数（[api/frontend.py:48](AFH_Competition-main/api/frontend.py#L48)），但 `agent/chat.py` 里**完全没用到**——勾选知识库无效。

目标：

1. **持久化**：用户上传文件后，自动解析、切片、向量化并落盘
2. **建立链接**：每个知识库 = 数据库一行 + 磁盘一个文件夹（同 ID）
3. **检索增强**：chat 时按用户勾选的 knowledge_ids 检索相关片段，拼到 LLM 的 system prompt
4. **CLI 脚本**：提供 `scripts/build_rag_index.py`，手动给任意文件/文件夹建索引（API 上传和 CLI 共享同一组核心函数）
5. **变更清单**：实施完成后产出 `MODIFIED_FILES.md`，列出所有改/新建的代码文件，方便他人 review

## 已确认的技术选型

| 维度 | 选择 | 备注 |
|---|---|---|
| Embedding | `sentence-transformers` + `BAAI/bge-small-zh-v1.5` | 中文优化，~100MB，本地推理，离线可用 |
| 向量库 | `faiss-cpu` + JSON 元数据 | Windows pip 直装；每 KB 一个目录 |
| 文件格式 | 纯文本类 + PDF + DOCX | 用 `pypdf`、`python-docx`；不做 xlsx |
| 存储位置 | `<data>/rag_index/<knowledge_id>/` | 复用 `AFH_DB_PATH` 同级目录，可由 `AFH_RAG_ROOT` 覆盖 |

每个知识库的磁盘结构：
```
D:\AFH_Competition\data\rag_index\<knowledge_id>\
  ├── index.faiss          # FAISS 向量索引（IndexFlatIP + L2 归一化 = cosine）
  ├── chunks.json          # 片段列表：[{chunk_id, text, source_file, char_start, char_end, file_hash}]
  ├── manifest.json        # 文件清单：[{filename, file_hash, chunk_count, uploaded_at, byte_size}]
  └── raw/                 # 保留上传原文件，便于将来回查/重建
```

## 新增模块结构 `agent/rag/`

| 文件 | 职责 |
|---|---|
| `__init__.py` | 暴露公共 API：`build_or_update_index`, `retrieve_safe`, `kb_store`, `append_context_to_system` |
| `config.py` | 常量、路径解析、环境变量（`AFH_RAG_ROOT`, `AFH_DISABLE_RAG_EMBEDDING`, `AFH_DISABLE_RAG`） |
| `loaders.py` | 按扩展名分发文件解析；单个文件失败不影响其他 |
| `chunker.py` | 中文友好的"段落优先 + 字符滑窗"切片（chunk=500 字，overlap=80） |
| `embedder.py` | **懒加载单例**；模型未装/下载失败/被禁用时降级为确定性 hash embedding |
| `store.py` | `KBStore` 类，封装 FAISS + chunks.json + manifest.json 读写 |
| `indexer.py` | 高层 API：`build_or_update_index`、`index_uploaded_bytes`（API 和 CLI 共用入口） |
| `retriever.py` | 高层 API：`retrieve_safe`（跨 KB 检索 + 聚合 + 兜底） |
| `prompt_format.py` | `append_context_to_system`：把检索结果格式化进 LLM system prompt |

设计原则：
- **import 时不加载任何重资源**——模型只在第一次 `get_embedder()` 时加载
- **失败永不让 chat 崩**——retrieve 抛任何异常都返回空，LLM 走无 RAG 路径
- **API 和 CLI 共享 `build_or_update_index(kb_id, paths)`**——保持单一真相源

## 修改既有文件

### `sql/schema.sql` — 末尾追加 `knowledge_bases` 表
```sql
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'personal',
    index_path TEXT NOT NULL DEFAULT '',
    file_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    file_type TEXT NOT NULL DEFAULT 'mixed',
    embedding_backend TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### [agent/database.py](AFH_Competition-main/agent/database.py) — 追加 5 个 CRUD
`create_knowledge_base`, `get_knowledge_base`, `list_knowledge_bases`, `update_knowledge_base_stats`, `delete_knowledge_base`。

### [api/frontend.py](AFH_Competition-main/api/frontend.py) — 5 处改动
1. **L16** 删除 `_personal_knowledge` 字典
2. **L237-265 `frontend_chat_stream`**：把 `request.knowledge_ids` 透传给 `chat.handle_chat`
3. **L308-313 `frontend_personal_knowledge`**：改读 `database.list_knowledge_bases("personal")`
4. **L316-333 `frontend_upload_knowledge`**：接收文件或文本 → 创建 KB → 调 `index_uploaded_bytes` → 更新 stats → 返回 `{id, files_indexed, chunks_added, embedding_backend}`
5. **L336-340 `frontend_delete_knowledge`**：先调 `kb_store(id).destroy()` 清磁盘，再删 DB 行

### [agent/chat.py](AFH_Competition-main/agent/chat.py) — 2 处改动
1. **`handle_chat`（L142）** 新增 `knowledge_ids: list[str] | None = None` 参数；调用 `retrieve_safe(message, knowledge_ids or [])`；把 `retrieved` 摘要写进 assistant message 的 metadata
2. **新增 `_build_system_prompt`**：用 `append_context_to_system` 把检索片段拼到 `CHAT_SYSTEM` 后面

> `api/main.py` 的 `/chat` 端点也调 `handle_chat`，因新参数有默认值，**无需改动**，老路径兼容。

### [requirements.txt](AFH_Competition-main/requirements.txt) — 追加
```
sentence-transformers==3.0.1
faiss-cpu==1.8.0
pypdf==5.0.1
python-docx==1.1.2
numpy==1.26.4
```

## 新增 CLI：`scripts/build_rag_index.py`

```bash
# 新建 KB 并索引文件夹
python scripts/build_rag_index.py --input D:/docs/618 --name "618规则库" --create

# 追加索引到已有 KB
python scripts/build_rag_index.py --input ./README.md --kb-id kb_xxx

# 同名文件覆盖
python scripts/build_rag_index.py --input D:/docs/618.pdf --kb-id kb_xxx --replace

# 列出所有 KB
python scripts/build_rag_index.py --list

# 删除 KB（DB 行 + 磁盘）
python scripts/build_rag_index.py --kb-id kb_xxx --delete
```

CLI 内部调用与 API 端点完全相同的 `agent.rag.build_or_update_index`。

## 关键技术细节

- **切片**：按 `\n\n` 切段 → 小段合并到 70% size → 大段字符滑窗（window=500, stride=420）
- **检索聚合**：对每个 KB 取 top-4，全局合并按分数排序截到 8，分数 < 0.2 丢弃
- **embedding 懒加载**：模块级只声明 `_model=None`；`get_embedder()` 双重检查 + lock；可选 `AFH_RAG_PRELOAD=1` 后台预热
- **重建策略**：同名同 hash 跳过；同名不同 hash + `--replace` 时删旧 chunks 全量重建 FAISS（IndexFlatIP 不支持就地删除，rebuild 几百毫秒可接受）
- **降级矩阵**：
  - sentence-transformers 缺/下载失败 → hash embedding，检索质量降但不报错
  - faiss 缺 → indexer skip 文件，前端提示
  - pypdf/docx 缺 → 该文件 skip，其他正常
  - chat 检索抛错 → `retrieve_safe` 返回 `[]`，LLM 走无 RAG

## 测试

新增：
- `tests/test_rag_chunker.py` — 纯函数单测
- `tests/test_rag_loaders.py` — mock 第三方依赖
- `tests/test_rag_prompt_format.py` — 格式化纯函数
- `tests/test_rag_indexer.py` — 用 `AFH_DISABLE_RAG_EMBEDDING=1` 走 hash 跑集成测
- `tests/test_rag_e2e.py` — 上传 → 列表 → chat → 删除完整链路

修改：
- `tests/conftest.py` 加 autouse fixture 默认设置 `AFH_DISABLE_RAG_EMBEDDING=1`，避免 CI 下模型

现有 `tests/test_frontend_api.py:70` 已经在 chat 请求里传 `knowledge_ids: []`，**新增的参数默认值与之兼容**。

## 实施完成后输出 `MODIFIED_FILES.md`（仓库根目录）

```markdown
# RAG 功能实现 — 变更文件清单

## 新增文件 (New)
- agent/rag/__init__.py — 包初始化
- agent/rag/config.py — 常量与路径
- agent/rag/loaders.py — 文件解析
- agent/rag/chunker.py — 文本切片
- agent/rag/embedder.py — 嵌入器（懒加载 + 降级）
- agent/rag/store.py — FAISS + JSON 落盘
- agent/rag/indexer.py — 索引构建入口
- agent/rag/retriever.py — 检索入口
- agent/rag/prompt_format.py — 上下文格式化
- scripts/build_rag_index.py — CLI 手动建索引
- tests/test_rag_chunker.py
- tests/test_rag_loaders.py
- tests/test_rag_prompt_format.py
- tests/test_rag_indexer.py
- tests/test_rag_e2e.py
- tests/conftest.py（若不存在）

## 修改文件 (Modified)
- sql/schema.sql — 追加 knowledge_bases 表
- agent/database.py — 5 个 CRUD 函数
- agent/chat.py — handle_chat 新增 knowledge_ids 参数，新增 _build_system_prompt
- api/frontend.py — 5 处：删内存字典 / chat_stream / personal / upload / delete
- requirements.txt — 5 个新依赖

## 未修改但需关注
- api/main.py — /chat 端点保持兼容（新参数默认值）
- ui/app.py — Streamlit 端未接入 RAG（v1 留给 React 前端）
- frontend/src/services/api.ts — 现有 uploadKnowledge 只发 text，文件上传需要前端 改造
```

## 端到端验证

```powershell
# 1. 装依赖（首次拉 ~500MB 含 torch）
.venv\Scripts\activate
pip install -r requirements.txt

# 2. 初始化 DB
python -c "from agent import database; database.init_db()"

# 3. 单测全过（hash embedding 模式，不下模型）
$env:AFH_DISABLE_LLM="1"; $env:AFH_DISABLE_RAG_EMBEDDING="1"
pytest tests/ -v

# 4. CLI 建索引（首次会下载 100MB 模型，~30 秒）
python scripts/build_rag_index.py --input ./README.md --name "本项目说明" --create
python scripts/build_rag_index.py --list

# 5. 启后端
uvicorn api.main:app --reload --port 8000

# 6. 启前端
cd frontend; npm install; npm run dev
# 或 streamlit run ui/app.py（但 Streamlit 端 v1 不接 RAG）

# 7. 在 React 前端勾选刚建的知识库，问"项目用了什么数据库？"
#    → 后端 chat assistant message 的 metadata.rag_chunks 应非空
#    → 回答应引用 SQLite

# 8. 重启后端再问一次，验证持久化
```

## 关键风险

1. **首次启动下载 100MB 模型** — 用户首次上传/聊天延迟 30-60 秒。缓解：日志显式提示 + 可选 `AFH_RAG_PRELOAD=1` 后台预热
2. **Python 3.13 没 faiss-cpu wheel** — README 建议 Python 3.10-3.12（本项目 venv 已经是 3.12）
3. **Streamlit UI 不接 RAG** — README 主推 React 前端，Streamlit 仅做 sidebar 提示引导
4. **并发写索引** — v1 假设单 worker（uvicorn 默认）；多 worker 时需加文件锁
5. **SSE 不是真流式** — 本次不重构，属另一个 PR

## 实施顺序

1. schema + database CRUD → 单测过
2. `rag/{config,chunker,loaders,prompt_format}`（纯函数）→ 单测过
3. `rag/{embedder,store}` → hash 模式集成测过
4. `rag/{indexer,retriever}` → 集成测过
5. `api/frontend.py` 5 处改动 → e2e 测过
6. `agent/chat.py` 接 retrieve → 验证 metadata
7. `scripts/build_rag_index.py` → 手测 list/create/delete/index
8. `requirements.txt` + README 更新 → 装真实模型跑完整链路
9. 写 `MODIFIED_FILES.md` 收尾

## 关键文件路径速查

- [agent/rag/](AFH_Competition-main/agent/rag/) — 新增包
- [api/frontend.py](AFH_Competition-main/api/frontend.py) — 主要 API 改动
- [agent/chat.py](AFH_Competition-main/agent/chat.py) — chat 接入检索
- [agent/database.py](AFH_Competition-main/agent/database.py) — KB 持久化
- [sql/schema.sql](AFH_Competition-main/sql/schema.sql) — 表定义
- [scripts/build_rag_index.py](AFH_Competition-main/scripts/build_rag_index.py) — CLI
- [requirements.txt](AFH_Competition-main/requirements.txt) — 依赖
