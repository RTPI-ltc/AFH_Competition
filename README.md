# 执行辅助 Agent

基于 LangGraph、FastAPI、Streamlit、DeepSeek API 和 SQLite 的电商活动规则执行辅助系统。项目面向珠宝集团运营场景，用项目、对话和上架清单承载运营工作流。

## 功能

- 解析活动规则文本，输出结构化规则列表
- 自动标注歧义、风险点和置信度
- 生成运营可执行检查清单、业务决策流程和边界反例
- 支持人工澄清后继续执行
- 支持项目增删，每个项目有独立上架清单
- 支持项目下多个对话，对话可增删
- 支持自然语言和 AI 交互，不再使用商品信息表单
- 支持 AI 根据对话增减上架清单商品
- 持久化项目、对话、消息、上架清单、规则解析和核查记录
- 未配置 DeepSeek API key 时，内置确定性 demo parser 仍可运行赛题示例

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置环境变量：

```bash
copy .env.example .env
```

编辑 `.env`，填入 `DEEPSEEK_API_KEY`。如果暂时不配置，系统会使用内置确定性逻辑演示核心流程。

3. 启动后端：

```bash
uvicorn api.main:app --reload --port 8000
```

4. 启动前端：

```bash
streamlit run ui/app.py
```

5. 访问：

- 前端 UI: http://localhost:8501
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 架构

```text
Streamlit UI -> FastAPI -> Agent Graph -> DeepSeek API or deterministic fallback
                              |
                              +-> project workspace
                              +-> conversation chat
                              +-> listing checklist
                              +-> rule_parser
                              +-> checklist_builder
                              +-> human_review_gate
                              +-> product_verifier
                              +-> SQLite persistence
```

## 数据库

默认使用 SQLite，不需要额外安装数据库服务。数据库文件会生成在 D 盘项目目录：

```text
D:\AFH_Competition\data\afh_agent.db
```

如果后续要把数据库或大文件放到其他 D 盘目录，可以设置：

```bash
set AFH_DB_PATH=D:\AFH_Competition\data\afh_agent.db
```

表结构在 `sql/schema.sql`，包含：

- `sessions`: 会话
- `chat_messages`: 聊天/操作历史
- `rule_runs`: 规则解析、清单和决策流程快照
- `products`: 商品信息
- `verification_runs`: 商品核查记录
- `projects`: 项目
- `conversations`: 项目下的对话
- `conversation_messages`: 新工作台聊天记录
- `listing_items`: 项目上架清单商品

## API

- `GET /projects`: 查看项目
- `POST /projects`: 创建项目
- `DELETE /projects/{project_id}`: 删除项目
- `GET /projects/{project_id}/conversations`: 查看项目对话
- `POST /conversations`: 创建对话
- `DELETE /conversations/{conversation_id}`: 删除对话
- `POST /chat`: 自然语言对话，AI 可增减上架清单
- `GET /projects/{project_id}/listing-items`: 查看项目上架清单
- `POST /projects/{project_id}/listing-items`: 手动创建上架清单项
- `DELETE /listing-items/{item_id}`: 移除上架清单项
- `POST /parse`: 解析规则文本并生成清单
- `POST /clarify`: 提交人工澄清答案并继续流程
- `POST /verify`: 核查商品是否满足活动规则
- `GET /sessions`: 查看最近会话
- `GET /sessions/{session_id}`: 查看单个会话历史

## 测试

```bash
pytest tests/ -v
```

测试覆盖赛题示例规则、边界值、品牌日互斥、人工接管、完整图执行流程和 SQLite 持久化。
