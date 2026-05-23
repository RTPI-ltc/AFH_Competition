# RAG 功能实现 — 变更文件清单

实施依据：`rag-rag-splendid-stonebraker.md`。

## 新增文件 (New)

### `agent/rag/` 包（核心 RAG 模块）
- `agent/rag/__init__.py` — 暴露 `build_or_update_index`、`retrieve_safe`、`kb_store`、`append_context_to_system` 等公共 API
- `agent/rag/config.py` — 常量、路径解析、`AFH_RAG_ROOT` / `AFH_DISABLE_RAG_EMBEDDING` / `AFH_DISABLE_RAG` / `AFH_RAG_PRELOAD` 环境变量
- `agent/rag/chunker.py` — 中文友好「段落优先 + 字符滑窗」切片（默认 chunk=500, overlap=80, merge_target=350）
- `agent/rag/loaders.py` — 按扩展名分发；支持 txt/md/rst/log/csv/tsv/json/yaml/html/pdf/docx；多编码兜底
- `agent/rag/embedder.py` — 懒加载单例 SentenceTransformer；失败/被禁用时降级为 hash embedding，永不抛错
- `agent/rag/store.py` — `KBStore` 类，封装 FAISS（缺失则 JSON 向量回退）、chunks.json、manifest.json、meta.json、raw/ 目录
- `agent/rag/indexer.py` — `build_or_update_index` / `index_uploaded_bytes` / `index_text`（API 和 CLI 共享入口），同 hash 跳过、`replace_same_name` 覆盖
- `agent/rag/retriever.py` — `retrieve_safe`：每 KB top-4、全局合并 top-8、分数 < 0.2 丢弃、任何异常降级返空
- `agent/rag/prompt_format.py` — `append_context_to_system` 把检索片段拼到 system prompt

### CLI 脚本
- `scripts/build_rag_index.py` — 手动建/追加/覆盖/列表/删除知识库；调用与 API 完全相同的 `build_or_update_index`

### 测试
- `tests/conftest.py` — autouse fixture 默认设置 `AFH_DISABLE_RAG_EMBEDDING=1`、`AFH_DISABLE_LLM=1`；`rag_tmp_root` fixture 隔离磁盘
- `tests/test_rag_chunker.py` — 切片纯函数单测
- `tests/test_rag_loaders.py` — 文件加载（含 UTF-8/GBK/JSON/PDF 缺包/目录遍历）
- `tests/test_rag_prompt_format.py` — 系统 prompt 拼接纯函数
- `tests/test_rag_indexer.py` — 走 hash backend 的索引 + 检索集成测
- `tests/test_rag_e2e.py` — 上传 → 列表 → chat（验 `rag_chunks` metadata）→ 删除完整链路

## 修改文件 (Modified)

- `sql/schema.sql` — 追加 `knowledge_bases` 表（id/name/description/type/index_path/file_count/chunk_count/file_type/embedding_backend/created_at/updated_at）
- `agent/database.py` — 新增 5 个 CRUD：`create_knowledge_base` / `get_knowledge_base` / `list_knowledge_bases` / `update_knowledge_base_stats` / `delete_knowledge_base`
- `agent/chat.py`：
  - `handle_chat` 新增 `knowledge_ids: list[str] | None = None` 参数
  - 新增 `_build_system_prompt` 调 `retrieve_safe` 后用 `append_context_to_system` 拼到 `CHAT_SYSTEM`
  - 新增 `_rag_summary` 把检索摘要写进 assistant message 的 `metadata.rag_chunks`
- `api/frontend.py` 5 处：
  1. 删除内存字典 `_personal_knowledge`，改导入 `agent.rag` 公共 API
  2. `frontend_chat_stream` 把 `request.knowledge_ids` 透传给 `chat.handle_chat`
  3. `frontend_personal_knowledge` 改读 `database.list_knowledge_bases("personal")`，回传 `file_count` / `chunk_count` / `embedding_backend`
  4. `frontend_upload_knowledge` 接收 `files`（multipart）或 `content`（文本）→ 创建 KB → `index_uploaded_bytes` → 回写 stats → 返回 `{id, files_indexed, chunks_added, embedding_backend, errors}`
  5. `frontend_delete_knowledge` 先 `kb_store(id).destroy()` 清磁盘，再 `database.delete_knowledge_base(id)`
- `requirements.txt` — 追加 `sentence-transformers==3.0.1` / `faiss-cpu==1.8.0` / `pypdf==5.0.1` / `python-docx==1.1.2` / `numpy==1.26.4`

## 未修改但需关注

- `api/main.py` — `/chat` 端点保持兼容（`handle_chat` 新参数有默认值）
- `ui/app.py` — Streamlit 端 v1 未接入 RAG（按方案）
- `frontend/src/services/api.ts` — 现有 `uploadKnowledge` 只发 `content` 文本；要支持文件上传需要前端继续改造（API 端已经支持 `files` 字段的 multipart）
- `tests/test_frontend_api.py:70` — 已经传 `knowledge_ids: []`，新参数默认值兼容，无需改动

## 落盘结构（每个知识库）

```
<AFH_RAG_ROOT 或 <AFH_DB_PATH 同级>/rag_index>/<knowledge_id>/
├── index.faiss        # faiss 装好时：FAISS IndexFlatIP + L2 归一化向量
├── index.json         # faiss 缺失时的 JSON 向量回退
├── chunks.json        # [{chunk_id, text, source_file, char_start, char_end, file_hash, metadata}]
├── manifest.json      # [{filename, file_hash, chunk_count, uploaded_at, byte_size, file_kind}]
├── meta.json          # 汇总统计 + embedding_backend
└── raw/               # 上传原文件保留
```

## 降级矩阵（关键容错）

| 缺失/禁用 | 行为 |
|---|---|
| `AFH_DISABLE_RAG_EMBEDDING=1` 或 `sentence-transformers` 未装/下载失败 | hash embedding（确定性、可检索但质量降低） |
| `faiss-cpu` / `numpy` 未装 | JSON 向量文件回退，纯 Python 余弦排序 |
| `pypdf` / `python-docx` 未装 | 对应文件 skip，其他正常索引 |
| chat 检索抛任何异常 | `retrieve_safe` 返回 `[]`，LLM 走无 RAG 路径 |
| `AFH_DISABLE_RAG=1` | `retrieve_safe` 直接返回 `[]` |

## 端到端验证（用户侧）

```powershell
# 1. 装依赖（首次拉 ~500MB 含 torch）
.venv\Scripts\activate
pip install -r requirements.txt

# 2. 初始化 DB
python -c "from agent import database; database.init_db()"

# 3. 单测全过（hash embedding 模式，不下模型）
$env:AFH_DISABLE_LLM="1"; $env:AFH_DISABLE_RAG_EMBEDDING="1"
pytest tests/ -v

# 4. CLI 建索引（首次会下载 ~100MB 模型）
python scripts/build_rag_index.py --input ./README.md --name "本项目说明" --create
python scripts/build_rag_index.py --list

# 5. 启后端 + 前端，在前端勾选刚建的知识库提问；assistant message 的
#    metadata.rag_chunks 应非空，回答应引用知识库内容
uvicorn api.main:app --reload --port 8000
cd frontend; npm install; npm run dev

# 6. 重启后端再问一次，验证持久化
```

## 本次冒烟（无 pytest 环境下手工验证）

- `python -c "from agent.rag import *"` 导入链路全部 OK
- `index_text("kb_smoke", "demo.txt", "...")` → 1 file / 1 chunk / hash-fallback
- `retrieve_safe("618 销量门槛", ["kb_smoke"])` → 命中 1 条
- `kb_store("kb_smoke").destroy()` → 清理 OK
- `database.create_knowledge_base/list/delete` round-trip → OK
