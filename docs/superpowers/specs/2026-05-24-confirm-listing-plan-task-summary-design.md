# Chatbox 确认上架方案 → 仅返回任务汇总

## 背景

当前 chatbox 的"确认方案"按钮会向后端发送固定文本 `确认执行上一个上架方案`，该文本目前走完整的 LLM 流程，返回包括 reply、recommendations、checklist、risks、confirmation 等在内的全套字段，并通过 `_apply_actions` 再次写入 `listing_items`。

由于 LLM 在初次提议时已经通过 `_apply_actions` 把推荐商品写入了 `listing_items`，再次走 LLM 会造成重复写入（冲突），且对用户而言"确认"动作展示的内容噪声过多。

## 目标

输入 `确认执行上一个上架方案` 时，chatbox 只返回**任务汇总**（仅"已确认上架清单"一段），不再渲染推荐 / 优先级分析 / 检查项 / 风险 / 确认按钮等卡片，也不再触发新的写入。

## 非目标

- 不改动"继续调整上一个上架方案"按钮的行为。
- 不改动右上角"任务汇总"按钮和 `/history/{task_id}/summarize` 接口的行为。
- 不改动 `_apply_actions` 在常规 LLM 回复中写入 `listing_items` 的逻辑。
- 不引入对触发文本的模糊匹配；仅精确匹配。

## 触发条件

`message.strip() == "确认执行上一个上架方案"`。其他文本（包括用户手工输入的 `确认方案`、`确认上架` 等）仍走原 LLM 流程。

## 后端改动（`agent/chat.py`）

### 新增常量

```python
CONFIRM_PLAN_TRIGGER = "确认执行上一个上架方案"
```

### 新增 `_build_task_summary`

读取当前 `listing_items`，与 catalog 按 `product_name` join 补 SKU 与分类。**只读、无副作用**。

```python
def _build_task_summary(project_id: str) -> dict[str, Any]:
    items = database.list_listing_items(project_id)
    by_name = {p["product_name"]: p for p in database.list_catalog_products(limit=2000)}
    enriched: list[dict[str, Any]] = []
    for it in items:
        p = by_name.get(it["product_name"]) or {}
        enriched.append({
            "product_name": it["product_name"],
            "status": it.get("status") or "",
            "notes": it.get("notes") or "",
            "sku_id": p.get("sku_id", ""),
            "category": " / ".join(
                x for x in [p.get("category_l1"), p.get("category_l2")] if x
            ),
        })
    return {"items": enriched, "total": len(enriched)}
```

### 在 `handle_chat` 中短路

在写入 user 消息**之后**、调 LLM **之前**插入：

```python
if message.strip() == CONFIRM_PLAN_TRIGGER:
    summary = _build_task_summary(project_id)
    if summary["total"]:
        reply = f"已为你汇总当前上架清单，共 {summary['total']} 条。"
    else:
        reply = "当前上架清单为空，请先让 Agent 推荐选品并加入清单后再确认。"
    metadata = {
        "event": "chat_reply",
        "actions": [],
        "applied_actions": [],
        "recommendations": [],
        "priority_analysis": [],
        "checklist": [],
        "risks": [],
        "needs_clarification": [],
        "confirmation": {"required": False},
        "rag_chunks": [],
        "knowledge_ids": list(knowledge_ids or []),
        "task_summary": summary,
    }
    database.add_conversation_message(conversation_id, "assistant", reply, metadata)
    return {
        "reply": reply,
        **metadata,
        "messages": database.list_conversation_messages(conversation_id),
        "listing_items": database.list_listing_items(project_id),
    }
```

要点：
- **不**调 `call_llm`、不调 `_apply_actions`：避免与既有写入路径冲突。
- 每次进入都重新读 `listing_items`：满足"每次都更新汇总"。
- 所有其他 metadata 列表字段置空：前端原有卡片在数组为空时本就不渲染。
- `event` 保持 `chat_reply`，与正常回复结构对齐。

## 前端改动

### `frontend/src/types.ts`

新增类型并扩展 `Message.metadata`：

```ts
export interface TaskSummaryItem {
  product_name: string;
  status: string;
  notes: string;
  sku_id: string;
  category: string;
}

export interface TaskSummary {
  items: TaskSummaryItem[];
  total: number;
}

// Message.metadata 增加可选字段：
// task_summary?: TaskSummary
```

### 新增 `frontend/src/components/Chat/TaskSummaryCard.tsx`

视觉与 `SummaryModal` 的"已确认上架清单"段落保持一致：标题展示"任务汇总 · 已确认上架清单（共 N 条）"；每条展示商品名、SKU、分类、状态、备注；`total === 0` 时显示空状态文案"当前上架清单为空"。

### `frontend/src/components/Chat/MessageList.tsx`

`AgentMessage` 中读取 `message.metadata?.task_summary`，若存在则渲染 `TaskSummaryCard`。其他卡片不需要改动——由于后端把对应数组置空、`confirmation.required` 为 false，它们的现有渲染条件自然为 false。

## 与既有功能的关系

- `/history/{task_id}/summarize`（右上角"任务汇总"按钮）：读取 conversation messages 聚合 metadata。新增的 `task_summary` 字段不会破坏其原有 key 的解析；该按钮行为不变。
- `_apply_actions`：仅在常规 LLM 回复中调用，本路径不触发。
- "继续调整上一个上架方案"按钮：发送的文本不是触发词，走原 LLM 流程，行为不变。

## 测试与验收

1. 在 chatbox 中先正常发起一轮选品请求，确认 LLM 返回带 confirmation。
2. 点击"确认方案" → 前端发送 `确认执行上一个上架方案`。
3. 验证返回的 assistant 消息：
   - reply 文本非空，符合上述两种文案之一。
   - 渲染**只有** `TaskSummaryCard`，没有推荐 / 优先级 / 检查项 / 风险 / 需要确认信息 / 确认按钮卡片。
   - `listing_items` 数量与上一轮相比**未变化**（确认本身不再写入）。
4. 再次点击"确认方案" → 新增一条汇总消息，内容反映当前最新 listing_items 快照。
5. 在两次确认之间手动通过 API 删除一条 listing_item，再点确认，汇总应反映删除后的状态。
6. 用户手工输入 `确认方案` 或 `确认` → 仍走 LLM 流程，验证未被误触发。
