# Chatbox 确认上架方案 → 仅返回任务汇总 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chatbox 收到精确文本 `确认执行上一个上架方案` 时短路 LLM，直接读取当前 `listing_items` 并以新的 `task_summary` metadata 字段返回；前端仅渲染一张"任务汇总"卡片，其他卡片自动隐藏。

**Architecture:** 后端在 `agent/chat.py:handle_chat` 入口处加触发判断 → 调用纯读函数 `_build_task_summary` → 返回与正常 chat_reply 同构、但其他列表全部为空、新增 `task_summary` 字段的 metadata。前端在 `Message.metadata` 上扩字段，新增 `TaskSummaryCard` 组件并在 `AgentMessage` 中按存在性渲染。

**Tech Stack:** Python 3 (FastAPI + SQLite + pytest 8.3.5)；TypeScript + React 19 + Vite + Tailwind v4。

**Spec:** `docs/superpowers/specs/2026-05-24-confirm-listing-plan-task-summary-design.md`

---

## File Structure

**Create:**
- `tests/__init__.py` — empty, makes pytest discover the package
- `tests/test_chat_confirm_summary.py` — backend tests for short-circuit behavior
- `frontend/src/components/Chat/TaskSummaryCard.tsx` — new render component

**Modify:**
- `agent/chat.py` — add `CONFIRM_PLAN_TRIGGER`, `_build_task_summary`, short-circuit in `handle_chat`
- `frontend/src/types/index.ts` — add `TaskSummaryItem`, `TaskSummary`; extend `Message.metadata`
- `frontend/src/components/Chat/MessageList.tsx` — read & render `task_summary`

---

## Task 1: Backend — failing tests for confirm-trigger short-circuit

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_chat_confirm_summary.py`

- [ ] **Step 1.1: Create empty test package file**

Create `tests/__init__.py` (empty file, 0 bytes).

- [ ] **Step 1.2: Write the failing test file**

Create `tests/test_chat_confirm_summary.py` with this exact content:

```python
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "afh_test.db"
    monkeypatch.setenv("AFH_DB_PATH", str(db_path))
    # Force module-level state to re-read env on next call.
    from agent import database

    database.init_db()
    yield db_path


@pytest.fixture()
def project_and_conv(temp_db):
    from agent import database

    project_id = database.ensure_project(str(uuid.uuid4()), name="测试项目")
    conv_id = database.ensure_conversation(project_id, str(uuid.uuid4()), title="测试会话")
    return project_id, conv_id


@pytest.fixture()
def seeded_catalog(temp_db):
    """Insert two products so _build_task_summary can join SKU/category."""
    from agent import database

    p1 = database.create_catalog_product({
        "sku_id": "SKU00001",
        "product_name": "古法金手镯 12g",
        "category_l1": "黄金",
        "category_l2": "手镯",
        "pricing_model": "weight",
        "weight_g": 12,
        "tag_price_rmb": 0,
        "list_price_rmb": 0,
        "stock": 50,
        "last_90d_sales": 30,
    })
    p2 = database.create_catalog_product({
        "sku_id": "SKU00002",
        "product_name": "钻石求婚戒指 30分",
        "category_l1": "钻石",
        "category_l2": "戒指",
        "pricing_model": "fixed",
        "tag_price_rmb": 8888,
        "list_price_rmb": 8888,
        "stock": 10,
        "last_90d_sales": 5,
    })
    return [p1, p2]


def test_confirm_trigger_short_circuits_and_returns_task_summary(
    project_and_conv, seeded_catalog, monkeypatch,
):
    from agent import chat, database

    project_id, conv_id = project_and_conv

    # Pre-populate listing_items so the summary has real content.
    database.add_listing_item(project_id, "古法金手镯 12g", status="拟上架", notes="主推")
    database.add_listing_item(project_id, "钻石求婚戒指 30分", status="待确认", notes="活动冲突待确认")

    # Trip-wire: any LLM call would fail the test.
    def _boom(*_a, **_kw):
        raise AssertionError("LLM must not be called on the confirm-trigger path")

    monkeypatch.setattr(chat, "call_llm", _boom)
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    result = chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")

    assert result["reply"]
    assert result["reply"].strip() != ""

    summary = result.get("task_summary")
    assert summary is not None
    assert summary["total"] == 2
    names = {item["product_name"] for item in summary["items"]}
    assert names == {"古法金手镯 12g", "钻石求婚戒指 30分"}
    skus = {item["sku_id"] for item in summary["items"]}
    assert skus == {"SKU00001", "SKU00002"}

    # Other cards must be suppressed.
    for key in ("recommendations", "priority_analysis", "checklist", "risks", "needs_clarification"):
        assert result.get(key) == [], f"expected empty {key}, got {result.get(key)!r}"
    assert result.get("confirmation") == {"required": False}


def test_confirm_trigger_does_not_write_listing_items(
    project_and_conv, seeded_catalog, monkeypatch,
):
    from agent import chat, database

    project_id, conv_id = project_and_conv
    database.add_listing_item(project_id, "古法金手镯 12g", status="拟上架")

    before = database.list_listing_items(project_id)

    monkeypatch.setattr(chat, "call_llm", lambda *_a, **_kw: pytest.fail("LLM called"))
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")
    chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")

    after = database.list_listing_items(project_id)
    assert len(after) == len(before), "confirm-trigger path must not write listing_items"


def test_confirm_trigger_empty_listing_returns_friendly_reply(
    project_and_conv, monkeypatch,
):
    from agent import chat

    project_id, conv_id = project_and_conv

    monkeypatch.setattr(chat, "call_llm", lambda *_a, **_kw: pytest.fail("LLM called"))
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    result = chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")

    assert result["task_summary"]["total"] == 0
    assert result["task_summary"]["items"] == []
    assert "为空" in result["reply"]


def test_non_trigger_message_still_goes_through_llm(project_and_conv, monkeypatch):
    from agent import chat

    project_id, conv_id = project_and_conv

    called = {"n": 0}

    def _fake_llm(*_a, **_kw):
        called["n"] += 1
        return '{"reply": "fake reply", "actions": [], "recommendations": []}'

    monkeypatch.setattr(chat, "call_llm", _fake_llm)
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    chat.handle_chat(project_id, conv_id, "确认方案")  # different text
    chat.handle_chat(project_id, conv_id, "你好")

    assert called["n"] == 2, "non-trigger messages must still call LLM"


def test_confirm_trigger_strips_whitespace(project_and_conv, monkeypatch):
    from agent import chat

    project_id, conv_id = project_and_conv

    monkeypatch.setattr(chat, "call_llm", lambda *_a, **_kw: pytest.fail("LLM called"))
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    result = chat.handle_chat(project_id, conv_id, "  确认执行上一个上架方案  ")
    assert result.get("task_summary") is not None
```

- [ ] **Step 1.3: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat_confirm_summary.py -v`
Expected: FAIL — `KeyError: 'task_summary'` or `assert result.get("task_summary") is not None` failing on every test (current `handle_chat` doesn't know about the trigger).

- [ ] **Step 1.4: Commit failing tests**

```bash
git add tests/__init__.py tests/test_chat_confirm_summary.py
git commit -m "test(chat): add failing tests for confirm-trigger task summary"
```

---

## Task 2: Backend — implement `_build_task_summary` and short-circuit

**Files:**
- Modify: `agent/chat.py`

- [ ] **Step 2.1: Add `CONFIRM_PLAN_TRIGGER` constant**

In `agent/chat.py`, find the line `BUSINESS_KEYWORDS = (` (around line 69) and insert this directly above it:

```python
CONFIRM_PLAN_TRIGGER = "确认执行上一个上架方案"
```

- [ ] **Step 2.2: Add `_build_task_summary` helper**

In `agent/chat.py`, insert this function directly above `def handle_chat(` (around line 546):

```python
def _build_task_summary(project_id: str) -> dict[str, Any]:
    """Snapshot the current listing for a project. Pure read — no writes, no LLM."""
    items = database.list_listing_items(project_id)
    by_name = {p["product_name"]: p for p in database.list_catalog_products(limit=2000)}
    enriched: list[dict[str, Any]] = []
    for it in items:
        product = by_name.get(it["product_name"]) or {}
        enriched.append({
            "product_name": it["product_name"],
            "status": it.get("status") or "",
            "notes": it.get("notes") or "",
            "sku_id": product.get("sku_id", ""),
            "category": " / ".join(
                part for part in [product.get("category_l1"), product.get("category_l2")] if part
            ),
        })
    return {"items": enriched, "total": len(enriched)}
```

- [ ] **Step 2.3: Insert short-circuit in `handle_chat`**

In `agent/chat.py`, find this exact existing block inside `handle_chat`:

```python
    database.add_conversation_message(
        conversation_id,
        "user",
        message,
        {"event": "chat", "knowledge_ids": kb_ids},
    )

    system_prompt, retrieved_chunks = _build_system_prompt(message, kb_ids)
```

Insert the short-circuit between the `add_conversation_message(... "user" ...)` call and the `system_prompt, retrieved_chunks = ...` line — i.e., immediately after the user message is persisted, before any LLM-related work:

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
            "knowledge_ids": kb_ids,
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

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat_confirm_summary.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 2.5: Commit backend implementation**

```bash
git add agent/chat.py
git commit -m "feat(chat): short-circuit confirm trigger to task summary (no LLM, no write)"
```

---

## Task 3: Frontend — extend types with `TaskSummary`

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 3.1: Add `TaskSummaryItem` and `TaskSummary` interfaces**

In `frontend/src/types/index.ts`, find this block (around lines 41-47):

```ts
export interface RecommendationItem {
  sku_id: string;
  product_name: string;
  priority: 'high' | 'medium' | 'low';
  score: number;
  reason: string;
}
```

Insert **after** the closing brace of `RecommendationItem`:

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
```

- [ ] **Step 3.2: Extend `Message.metadata` with `task_summary`**

In the same file, find the `Message` interface (lines 3-17). Replace the existing `metadata` field block with one that adds `task_summary`:

Old:
```ts
  metadata?: {
    checklist?: CheckListItem[];
    risks?: RiskItem[];
    needs_clarification?: string[];
    recommendations?: RecommendationItem[];
    priority_analysis?: string[];
    confirmation?: ConfirmationRequest;
    rag_chunks?: RagChunk[];
    knowledge_ids?: string[];
  };
```

New:
```ts
  metadata?: {
    checklist?: CheckListItem[];
    risks?: RiskItem[];
    needs_clarification?: string[];
    recommendations?: RecommendationItem[];
    priority_analysis?: string[];
    confirmation?: ConfirmationRequest;
    rag_chunks?: RagChunk[];
    knowledge_ids?: string[];
    task_summary?: TaskSummary;
  };
```

- [ ] **Step 3.3: Typecheck**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TS errors.

- [ ] **Step 3.4: Commit types update**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add TaskSummary types for confirm-trigger response"
```

---

## Task 4: Frontend — create `TaskSummaryCard` component

**Files:**
- Create: `frontend/src/components/Chat/TaskSummaryCard.tsx`

- [ ] **Step 4.1: Create the component file**

Create `frontend/src/components/Chat/TaskSummaryCard.tsx` with this exact content:

```tsx
import { FileBarChart, Package } from 'lucide-react';
import type { TaskSummary } from '../../types';

interface TaskSummaryCardProps {
  summary: TaskSummary;
}

export function TaskSummaryCard({ summary }: TaskSummaryCardProps) {
  return (
    <div className="mt-3 border border-emerald-200 rounded-xl overflow-hidden">
      <div className="px-4 py-2 bg-emerald-50 border-b border-emerald-200 flex items-center gap-2">
        <FileBarChart size={15} className="text-emerald-600" />
        <h4 className="text-sm font-semibold text-emerald-700">
          任务汇总 · 已确认上架清单（共 {summary.total} 条）
        </h4>
      </div>
      {summary.total === 0 ? (
        <p className="px-4 py-6 text-sm text-gray-400 text-center">
          当前上架清单为空。
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {summary.items.map((item, idx) => (
            <li key={`${item.sku_id || item.product_name}-${idx}`} className="px-4 py-3">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 bg-emerald-100 rounded-lg flex items-center justify-center shrink-0">
                  <Package size={14} className="text-emerald-700" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-800">{item.product_name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {[item.sku_id, item.category].filter(Boolean).join(' · ') || '—'}
                  </p>
                  <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                    {item.status && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {item.status}
                      </span>
                    )}
                    {item.notes && (
                      <span className="text-xs text-gray-600">{item.notes}</span>
                    )}
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4.2: Typecheck the new component compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds.

(The component isn't imported yet, so TS may flag it as unused — that's fine; the next task wires it in. Skip the commit until after Task 5 so the component lands together with its consumer.)

---

## Task 5: Frontend — render `TaskSummaryCard` in `AgentMessage`

**Files:**
- Modify: `frontend/src/components/Chat/MessageList.tsx`

- [ ] **Step 5.1: Import the new card**

In `frontend/src/components/Chat/MessageList.tsx`, find this import line (line 5):

```tsx
import { RagSourcesCard } from './RagSourcesCard';
```

Add a new import line directly under it:

```tsx
import { TaskSummaryCard } from './TaskSummaryCard';
```

- [ ] **Step 5.2: Import the `TaskSummary` type**

In the same file, find this import line (line 2):

```tsx
import type { ConfirmationRequest, Message, RagChunk, RecommendationItem } from '../../types';
```

Replace it with:

```tsx
import type { ConfirmationRequest, Message, RagChunk, RecommendationItem, TaskSummary } from '../../types';
```

- [ ] **Step 5.3: Read `task_summary` from metadata**

In the same file, find this block inside `AgentMessage` (around lines 35-42):

```tsx
  const checklist = message.metadata?.checklist;
  const risks = message.metadata?.risks;
  const needsClarification = message.metadata?.needs_clarification;
  const recommendations = message.metadata?.recommendations as RecommendationItem[] | undefined;
  const priorityAnalysis = message.metadata?.priority_analysis;
  const confirmation = message.metadata?.confirmation as ConfirmationRequest | undefined;
  const ragChunks = message.metadata?.rag_chunks as RagChunk[] | undefined;
  const knowledgeIds = message.metadata?.knowledge_ids as string[] | undefined;
```

Add this line immediately after `knowledgeIds`:

```tsx
  const taskSummary = message.metadata?.task_summary as TaskSummary | undefined;
```

- [ ] **Step 5.4: Render the card**

In the same file, find this block (around lines 176-178):

```tsx
          {ragChunks && ragChunks.length > 0 && (
            <RagSourcesCard chunks={ragChunks} knowledgeIds={knowledgeIds} />
          )}
```

Insert directly **above** it:

```tsx
          {taskSummary && (
            <TaskSummaryCard summary={taskSummary} />
          )}
```

- [ ] **Step 5.5: Typecheck and lint**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TS errors.

Run: `cd frontend && npm run lint`
Expected: no errors (warnings on unrelated files are acceptable; do not silence new warnings introduced by this change).

- [ ] **Step 5.6: Commit frontend component + wiring together**

```bash
git add frontend/src/components/Chat/TaskSummaryCard.tsx frontend/src/components/Chat/MessageList.tsx
git commit -m "feat(chat-ui): render TaskSummaryCard for confirm-trigger response"
```

---

## Task 6: End-to-end manual verification

**Files:** none modified.

- [ ] **Step 6.1: Start the backend**

Run (from repo root): `uvicorn api.main:app --reload --port 8000`
Expected: server starts without errors.

- [ ] **Step 6.2: Start the frontend dev server**

In a separate terminal: `cd frontend && npm run dev`
Expected: Vite dev server starts and prints a local URL.

- [ ] **Step 6.3: Reproduce the original flow**

In the browser:
1. Open the app, select or create a project.
2. Send a normal selection request, e.g. "推荐 2 个钻石戒指上架"。
3. Wait for the agent to return a plan that includes the "确认方案 / 继续调整" buttons.

- [ ] **Step 6.4: Click 确认方案 and verify task-summary-only render**

Click **确认方案**.

Expected agent message:
- A non-empty reply line like "已为你汇总当前上架清单，共 N 条。"
- Exactly one card visible: the green "任务汇总 · 已确认上架清单（共 N 条）" card.
- **No** 推荐上架商品 / 优先级分析 / 检查清单 / 风险 / 需要人工确认 / 等待确认 卡片渲染。

- [ ] **Step 6.5: Verify no duplicate writes**

Open the listing items panel (or call `GET /projects/{project_id}/listing-items`).
Expected: item count unchanged between before and after clicking 确认方案 — count should match what was written when the plan was first proposed.

- [ ] **Step 6.6: Verify "更新" behavior on a second click**

Click **确认方案** a second time.
Expected:
- A second agent message appears, also containing only the 任务汇总 card.
- The card reflects the **current** listing_items state.

Optional: delete one listing item via API (`DELETE /listing-items/{item_id}`), then click 确认方案 again. The new card should reflect the new (smaller) count.

- [ ] **Step 6.7: Verify negative cases**

Type and send the message `确认方案` (handwritten, not via button).
Expected: this still goes through the normal LLM flow — recommendations / checklist / confirmation buttons render as before.

- [ ] **Step 6.8: No commit needed for manual verification**

If any verification step fails, return to the relevant earlier task and fix.
