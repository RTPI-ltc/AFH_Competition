from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "afh_agent.db"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


def get_db_path() -> Path:
    configured = os.getenv("AFH_DB_PATH")
    return Path(configured) if configured else DEFAULT_DB_PATH


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def connect() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> Path:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(schema)
    return get_db_path()


def create_session(title: str | None = None) -> str:
    init_db()
    session_id = str(uuid.uuid4())
    clean_title = (title or "新会话").strip()[:80] or "新会话"
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)",
            (session_id, clean_title),
        )
    return session_id


def create_project(name: str, description: str = "") -> str:
    init_db()
    project_id = str(uuid.uuid4())
    clean_name = name.strip()[:120] or "新项目"
    with connect() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description) VALUES (?, ?, ?)",
            (project_id, clean_name, description.strip()),
        )
    return project_id


def list_projects() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, description, created_at, updated_at
            FROM projects
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def ensure_project(project_id: str | None = None, name: str | None = None) -> str:
    init_db()
    if project_id:
        with connect() as conn:
            row = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row:
                return project_id
    projects = list_projects()
    if projects and not name:
        return projects[0]["id"]
    return create_project(name or "默认项目")


def update_project(project_id: str, name: str, description: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE projects
            SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name.strip()[:120] or "未命名项目", description.strip(), project_id),
        )


def delete_project(project_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def touch_project(project_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )


def create_conversation(project_id: str, title: str | None = None) -> str:
    init_db()
    conversation_id = str(uuid.uuid4())
    clean_title = (title or "新对话").strip()[:120] or "新对话"
    with connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, project_id, title) VALUES (?, ?, ?)",
            (conversation_id, project_id, clean_title),
        )
    touch_project(project_id)
    return conversation_id


def list_conversations(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, title, created_at, updated_at
            FROM conversations
            WHERE project_id = ?
            ORDER BY updated_at DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def ensure_conversation(project_id: str, conversation_id: str | None = None, title: str | None = None) -> str:
    init_db()
    if conversation_id:
        with connect() as conn:
            row = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND project_id = ?",
                (conversation_id, project_id),
            ).fetchone()
            if row:
                return conversation_id
    conversations = list_conversations(project_id)
    if conversations and not title:
        return conversations[0]["id"]
    return create_conversation(project_id, title)


def delete_conversation(conversation_id: str) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT project_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    if row:
        touch_project(row["project_id"])


def touch_conversation(conversation_id: str) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT project_id FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )
    if row:
        touch_project(row["project_id"])


def add_conversation_message(
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO conversation_messages (conversation_id, role, content, metadata_json)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, _json(metadata or {})),
        )
        message_id = int(cursor.lastrowid)
    touch_conversation(conversation_id)
    return message_id


def list_conversation_messages(conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, conversation_id, role, content, metadata_json, created_at
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()
    return [
        {**dict(row), "metadata": json.loads(row["metadata_json"])}
        for row in rows
    ]


def add_listing_item(
    project_id: str,
    product_name: str,
    details: dict[str, Any] | None = None,
    status: str = "待确认",
    notes: str = "",
    source_conversation_id: str | None = None,
) -> str:
    init_db()
    item_id = str(uuid.uuid4())
    name = product_name.strip()[:160] or "未命名商品"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO listing_items (
                id, project_id, product_name, status, details_json,
                source_conversation_id, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (item_id, project_id, name, status.strip() or "待确认", _json(details or {}), source_conversation_id, notes.strip()),
        )
    touch_project(project_id)
    return item_id


def list_listing_items(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, product_name, status, details_json,
                   source_conversation_id, notes, created_at, updated_at
            FROM listing_items
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,),
        ).fetchall()
    return [
        {**dict(row), "details": json.loads(row["details_json"])}
        for row in rows
    ]


def update_listing_item(item_id: str, status: str | None = None, notes: str | None = None) -> None:
    assignments: list[str] = []
    values: list[Any] = []
    if status is not None:
        assignments.append("status = ?")
        values.append(status)
    if notes is not None:
        assignments.append("notes = ?")
        values.append(notes)
    if not assignments:
        return
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(item_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE listing_items SET {', '.join(assignments)} WHERE id = ?",
            values,
        )


def delete_listing_item(item_id: str) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT project_id FROM listing_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        conn.execute("DELETE FROM listing_items WHERE id = ?", (item_id,))
    if row:
        touch_project(row["project_id"])


def _next_product_code(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT product_code
        FROM product_catalog
        WHERE product_code LIKE 'SP%'
        ORDER BY product_code DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return "SP000001"
    try:
        number = int(str(row["product_code"])[2:]) + 1
    except ValueError:
        number = 1
    return f"SP{number:06d}"


def create_catalog_product(data: dict[str, Any]) -> str:
    init_db()
    product_id = str(uuid.uuid4())
    with connect() as conn:
        product_code = _next_product_code(conn)
        conn.execute(
            """
            INSERT INTO product_catalog (
                id, product_code, name, category, brand, sku, price,
                stock, sales_30d, rating, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                product_code,
                str(data.get("name") or "未命名商品").strip()[:160],
                str(data.get("category") or "").strip(),
                str(data.get("brand") or "").strip(),
                str(data.get("sku") or "").strip(),
                float(data.get("price") or 0),
                int(data.get("stock") or 0),
                int(data.get("sales_30d") or 0),
                float(data.get("rating") or 0),
                str(data.get("status") or "在售").strip(),
                str(data.get("notes") or "").strip(),
            ),
        )
    return product_id


def list_catalog_products(query: str = "", limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    q = f"%{query.strip()}%"
    with connect() as conn:
        if query.strip():
            rows = conn.execute(
                """
                SELECT *
                FROM product_catalog
                WHERE product_code LIKE ? OR name LIKE ? OR category LIKE ? OR brand LIKE ? OR sku LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (q, q, q, q, q, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *
                FROM product_catalog
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_catalog_product(product_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM product_catalog WHERE id = ?", (product_id,)).fetchone()
    return dict(row) if row else None


def update_catalog_product(product_id: str, data: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE product_catalog
            SET name = ?, category = ?, brand = ?, sku = ?, price = ?,
                stock = ?, sales_30d = ?, rating = ?, status = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                str(data.get("name") or "未命名商品").strip()[:160],
                str(data.get("category") or "").strip(),
                str(data.get("brand") or "").strip(),
                str(data.get("sku") or "").strip(),
                float(data.get("price") or 0),
                int(data.get("stock") or 0),
                int(data.get("sales_30d") or 0),
                float(data.get("rating") or 0),
                str(data.get("status") or "在售").strip(),
                str(data.get("notes") or "").strip(),
                product_id,
            ),
        )


def delete_catalog_product(product_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM product_catalog WHERE id = ?", (product_id,))


def ensure_session(session_id: str | None, title: str | None = None) -> str:
    init_db()
    if not session_id:
        return create_session(title)
    with connect() as conn:
        row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row:
            return session_id
    return create_session(title)


def touch_session(session_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )


def log_message(session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, metadata_json)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, _json(metadata or {})),
        )
    touch_session(session_id)


def save_rule_run(session_id: str, stage: str, state: dict[str, Any]) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO rule_runs (
                session_id, stage, raw_rules, parsed_rules_json, risk_points_json,
                clarification_questions_json, clarification_answers_json, checklist_json,
                decision_flow_json, counter_examples_json, final_decision
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                stage,
                state.get("raw_rules", ""),
                _json(state.get("parsed_rules", [])),
                _json(state.get("risk_points", [])),
                _json(state.get("clarification_questions", [])),
                _json(state.get("clarification_answers", {})),
                _json(state.get("checklist", [])),
                _json(state.get("decision_flow", [])),
                _json(state.get("counter_examples", [])),
                state.get("final_decision", ""),
            ),
        )
        run_id = int(cursor.lastrowid)
    touch_session(session_id)
    return run_id


def save_product(session_id: str, product_input: dict[str, Any]) -> str:
    product_id = str(uuid.uuid4())
    name = str(product_input.get("name") or "未命名商品")[:120]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO products (id, session_id, name, product_json)
            VALUES (?, ?, ?, ?)
            """,
            (product_id, session_id, name, _json(product_input)),
        )
    touch_session(session_id)
    return product_id


def save_verification_run(
    session_id: str,
    product_id: str | None,
    product_input: dict[str, Any],
    state: dict[str, Any],
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO verification_runs (
                session_id, product_id, product_input_json,
                verification_result_json, final_decision
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                product_id,
                _json(product_input),
                _json(state.get("verification_result", [])),
                state.get("final_decision", ""),
            ),
        )
        run_id = int(cursor.lastrowid)
    touch_session(session_id)
    return run_id


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_session_history(session_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        session = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        messages = conn.execute(
            """
            SELECT role, content, metadata_json, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
        products = conn.execute(
            """
            SELECT id, name, product_json, created_at, updated_at
            FROM products
            WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()
        verifications = conn.execute(
            """
            SELECT id, product_id, product_input_json, verification_result_json, final_decision, created_at
            FROM verification_runs
            WHERE session_id = ?
            ORDER BY id DESC
            """,
            (session_id,),
        ).fetchall()
    return {
        "session": dict(session) if session else None,
        "messages": [
            {**dict(row), "metadata": json.loads(row["metadata_json"])}
            for row in messages
        ],
        "products": [
            {**dict(row), "product": json.loads(row["product_json"])}
            for row in products
        ],
        "verifications": [
            {
                **dict(row),
                "product_input": json.loads(row["product_input_json"]),
                "verification_result": json.loads(row["verification_result_json"]),
            }
            for row in verifications
        ],
    }
