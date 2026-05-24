# AFH Competition Execution Assistant

面向电商活动运营场景的执行辅助 Agent。项目当前主推 `next` 分支版本：React 前端 + FastAPI 后端 + SQLite 持久化 + DeepSeek/OpenAI-compatible LLM 调用适配。

系统用于把活动规则、商品 SKU、知识库和项目对话串成一个可执行工作台，帮助运营人员完成规则理解、上架清单维护、商品主数据管理和活动执行检查。

## 当前能力

- 项目工作台：支持项目、任务/对话、历史记录的创建、切换、重命名和删除。
- AI 对话：围绕当前项目进行自然语言沟通，可自动维护上架清单。
- SKU 品类库：使用 SQLite 存储商品主数据，SKU 编号自动生成，内置 20 条虚构品牌样例数据。
- 商品管理：支持按品类和关键词查询，支持新增/删除 SKU。
- 知识库：支持官方知识库和用户知识库。
- 多模态导入：知识库导入支持文本、PDF、Office、图片、音频、视频等附件；可抽取文本的文件会合并为知识库内容，多模态素材会保存元数据。
- 规则链路：保留 LangGraph 规则解析、清单生成、人工澄清、商品核查等后端能力。
- 降级可用：未配置 `DEEPSEEK_API_KEY` 时，系统仍可使用确定性 fallback 演示核心流程。

## 技术栈

- Frontend: React 19, TypeScript, Vite, Tailwind CSS, lucide-react
- Backend: FastAPI, Pydantic, LangGraph
- LLM: DeepSeek chat API, 兼容 OpenAI SDK 调用方式
- Database: SQLite
- Legacy demo UI: Streamlit 仍保留在 `ui/app.py`，但当前推荐使用 React 前端

## 目录结构

```text
D:\AFH_Competition
├── agent/                 # Agent 业务逻辑、LLM 适配、数据库访问、LangGraph 节点
├── api/                   # FastAPI 后端
│   ├── main.py            # 后端入口
│   └── frontend.py        # React 前端兼容 API
├── frontend/              # React + Vite 前端
├── sql/schema.sql         # SQLite 表结构
├── tests/                 # 后端测试
├── data/                  # 本地 SQLite 数据库，已被 .gitignore 忽略
├── requirements.txt       # Python 依赖
└── README.md
```

## 快速启动

### 1. 安装 Python 依赖

```powershell
pip install -r requirements.txt
```

如果使用 Codex 桌面内置 Python，也可以显式执行：

```powershell
& "C:\Users\sunri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pip install -r requirements.txt
```

### 2. 配置 API Key

```powershell
copy .env.example .env
```

编辑 `.env`，填入：

```text
DEEPSEEK_API_KEY=your-api-key-here
```

不配置时，系统会使用 fallback 逻辑，适合本地演示和测试。

### 3. 启动后端

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

后端地址：

- Health: http://127.0.0.1:8000/api/health
- API Docs: http://127.0.0.1:8000/docs

### 4. 安装并启动前端

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

前端地址：

- React UI: http://127.0.0.1:5173

Vite 已将 `/api` 代理到 `http://localhost:8000`。

## 数据库

默认使用 SQLite，数据库文件位于：

```text
D:\AFH_Competition\data\afh_agent.db
```

可以通过环境变量覆盖：

```powershell
set AFH_DB_PATH=D:\AFH_Competition\data\afh_agent.db
```

主要表：

- `projects`: 项目
- `conversations`: 项目下的任务/对话
- `conversation_messages`: 对话消息
- `listing_items`: 项目上架清单
- `product_catalog`: SKU 商品主数据
- `sessions`, `chat_messages`, `rule_runs`, `products`, `verification_runs`: 规则解析和商品核查历史

`product_catalog` 当前字段覆盖 SKU 编号、商品名称、品牌、一级/二级类目、定价模式、克重、成色、钻石参数、吊牌价、活动价、历史最低价、库存、90 天销量、好评率、退货率、证书、工厂和活动信息。

本地启动时会自动初始化数据库，并在商品表为空时写入 20 条虚构品牌样例 SKU。样例品牌不使用真实品牌。

## 前端 API

React 前端使用 `/api` 前缀：

- `GET /api/projects`: 项目列表
- `POST /api/projects?name=...`: 创建项目
- `PUT /api/projects/{project_id}/rename?name=...`: 重命名项目
- `POST /api/task/new?project_id=...`: 开启新任务
- `GET /api/history?project_id=...`: 当前项目任务历史
- `GET /api/history/{task_id}`: 任务详情
- `DELETE /api/history/{task_id}`: 删除任务
- `POST /api/chat/stream`: SSE 对话流
- `GET /api/products`: SKU 商品列表
- `POST /api/products`: 新增 SKU 商品
- `DELETE /api/products/{sku_id}`: 删除 SKU 商品
- `GET /api/knowledge/official`: 官方知识库
- `GET /api/knowledge/personal`: 用户知识库
- `POST /api/knowledge/upload`: 导入知识库，支持多模态附件
- `DELETE /api/knowledge/{knowledge_id}`: 删除用户知识库

旧版接口仍保留：

- `GET /projects`
- `POST /projects`
- `POST /chat`
- `GET /catalog/products`
- `POST /parse`
- `POST /clarify`
- `POST /verify`

## 知识库多模态导入

前端导入知识库时可选择文件或文件夹，也可以直接粘贴文本。

支持类型：

- 文本：`.txt`, `.md`, `.json`, `.csv`, `.tsv`, `.xml`, `.yaml`, `.html`, `.py`, `.js`, `.ts`
- 文档：`.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`
- 图片：`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`, `.svg`
- 音频：`.mp3`, `.wav`, `.m4a`
- 视频：`.mp4`, `.mov`, `.avi`, `.webm`

当前后端会对文本、`.docx`、`.xlsx` 做基础文本抽取；图片、音频、视频等多模态素材会保存文件名、类型、大小、模态类型和必要元数据。后续接入真正 RAG 或多模态模型时，可以直接使用这些元数据和附件内容扩展索引链路。

## 开发与验证

## 风控机制

当前版本在模型输出后增加了业务风控审计，尽量不影响 RAG 检索链路：

- 输出合规：拦截“保证升值”“全网最低”“零风险”等绝对承诺或极限表述。
- 价格一致性：识别回复中的金额，并与被引用 SKU 的商品库价格做一致性校验。
- 商品风险：对活动互斥、价格保护、库存偏低、好评率偏低、退货率偏高、证书缺失做确定性检查。
- 动作阻断：如果本轮存在高风险项，并且模型试图执行上架/移除动作，本轮动作会被阻断并要求人工确认。
- 事件留痕：风控审计结果以 JSONL 形式写入 `data/risk_events/`，该目录已被 `.gitignore` 忽略。

风控结果会进入聊天消息 metadata 的 `risk_control` 字段，并同步转为前端可展示的 `risks` 与 `needs_clarification`。

## TypeScript SDK

独立 SDK 位于：

```text
sdk/typescript
```

本地类型检查：

```powershell
& "D:\AFH_Competition\frontend\node_modules\.bin\tsc.cmd" -p sdk\typescript\tsconfig.json --noEmit
```

SDK 封装项目、任务历史、SSE 对话流、商品库、知识库、项目汇总等接口；`ChatMetadata.risk_control` 会暴露风控审计结果。

后端测试：

```powershell
pytest tests\ -v
```

前端构建：

```powershell
cd frontend
npm run build
```

当前验证状态：

- `pytest tests\ -v`: 16 passed
- `npm run build`: passed

## Git 分支

- `main`: 已合并 React 前端和后端兼容层的稳定基础版。
- `next`: 在 `main` 基础上修复多模态知识库导入和新任务创建流程，当前推荐体验分支。

## 注意事项

- `.env`、`data/*.db`、`node_modules/`、`frontend/dist/`、日志文件和缓存目录不会提交到 Git。
- 大文件和本地数据库默认放在 `D:\AFH_Competition` 下，避免占用 C 盘。
- 如果前端请求失败，先确认后端 `http://127.0.0.1:8000/api/health` 是否返回 `{"status":"ok"}`。
