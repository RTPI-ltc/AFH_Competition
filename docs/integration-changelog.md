# 迭代整合说明

> 整合日期：2025-05-23
> 远程分支：`origin/next` (commit `7d832ca`)
> 本地基线：`main` (commit `1440627`)

---

## 整合策略

采用 **选择性合并** 策略：从 `origin/next` 拉取业务逻辑和前端更新，同时保留本地独立开发的 SDK 封装层和文档体系。

核心原则：
- 远程的业务代码（chat、database、frontend API）直接覆盖更新
- 本地 SDK 层（`sdk/`）和工具层（`agent/tools/`）保持不变
- 存在冲突的文件（`agent/llm.py`、`requirements.txt`）手动合并
- `docs/` 目录全部保持本地状态

---

## 远程分支引入的变更

### 新增功能

| 提交 | 说明 |
|------|------|
| `3d78620` | 商品目录替换为 SKU 数据库（珠宝领域 schema） |
| `6d792e6` | React + TypeScript + Vite 前端集成 |
| `45aaaab` | 多模态知识上传 + 新任务流 |
| `f6e1160` | 可确认的上架推荐流程 |
| `3fe31f9` | 阿里云/通义千问 LLM Provider 支持 |
| `4695e38` | 聊天框响应走 LLM 路由 |

### Bug 修复

| 提交 | 说明 |
|------|------|
| `7d832ca` | 稳定任务流和聊天解析 |
| `d4b7ef6` | 阿里云 LLM 调用容错增强 |
| `f8b614e` | 轻量级 prompt 防止 stream 挂起 |

---

## 合并后文件结构

```
backend/
├── agent/
│   ├── llm.py            ← 合并：多 Provider + SDK 桥接
│   ├── chat.py           ← 远程更新：重构后的任务流
│   ├── database.py       ← 远程更新：SKU schema + 迁移
│   ├── graph.py          ← 本地保持
│   └── tools/            ← 本地保持（SDK tool 示例）
│       ├── __init__.py
│       └── stock.py
├── sdk/                  ← 本地保持（SDK 封装层）
│   ├── __init__.py
│   ├── client.py         # AsyncOpenAI 异步客户端
│   ├── config.py         # pydantic-settings 配置
│   ├── errors.py         # 错误分类 + 重试装饰器
│   ├── observability.py  # 调用追踪
│   ├── session.py        # 会话持久化
│   ├── streaming.py      # SSE 流式处理
│   └── tools.py          # @tool 装饰器 + ToolRegistry
├── api/
│   ├── main.py           ← 远程更新：CORS + 前端路由
│   └── frontend.py       ← 远程更新：知识管理 + 流式聊天 + PDF 提取
├── frontend/             ← 远程新增：React 前端应用
├── sql/
│   └── schema.sql        ← 远程更新：珠宝 SKU 表结构
├── tests/                ← 远程更新：24 个测试全部通过
├── ui/
│   └── app.py            ← 远程更新：Streamlit UI
└── requirements.txt      ← 合并：全部依赖
```

---

## 关键合并点

### 1. `agent/llm.py`（手动合并）

合并了两个方向的改动：

**来自远程：**
- 多 Provider 架构（`PROVIDER_DEFAULTS` 字典，支持 deepseek / aliyun）
- 环境变量驱动的配置（`LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_MODEL`）
- 可配置 timeout 和 max_tokens
- `parse_llm_json()` 增加容错解析（fallback 扫描首个 JSON 对象）

**来自本地：**
- `call_llm_via_sdk()` 同步桥接函数，供现有节点渐进迁移到 SDK 层

### 2. `requirements.txt`（手动合并）

最终依赖列表：

| 包 | 版本 | 来源 |
|----|------|------|
| pydantic-settings | 2.7.1 | 本地 SDK 层 |
| sse-starlette | 2.2.1 | 本地 SDK 层 |
| python-multipart | 0.0.20 | 远程（文件上传） |
| pypdf | 6.10.0 | 远程（PDF 文本提取） |

其余依赖两端一致，无冲突。

---

## 本地保留未动的部分

| 路径 | 说明 |
|------|------|
| `sdk/` | 完整的 LLM SDK 封装层（7 个模块） |
| `agent/tools/` | SDK tool 注册示例（stock、campaign） |
| `docs/` | 架构文档、SDK 规划、设计 spec 等 |

---

## 验证结果

```
$ python -m pytest tests/ -v
======================= 24 passed, 2 warnings in 5.56s ========================
```

所有模块导入正常，无运行时错误。

---

## 后续工作

1. **SDK 层与新 chat 流程对接** — `agent/chat.py` 重构后可直接使用 `call_llm_via_sdk()` 替换同步调用
2. **流式端点接入 SDK StreamHandler** — `api/frontend.py` 的 SSE 流可迁移到 `sdk/streaming.py`
3. **Tool Calling 集成** — 将 `agent/tools/` 中的工具通过 `sdk/client.py` 的 `call_with_tools()` 接入决策流程
4. **前端联调** — `frontend/` 已就绪，需 `npm install && npm run dev` 启动
