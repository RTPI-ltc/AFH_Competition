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
        existing_catalog = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'product_catalog'"
        ).fetchone()
        if existing_catalog:
            _migrate_product_catalog(conn)
        conn.executescript(schema)
        _migrate_product_catalog(conn)
    return get_db_path()


def _migrate_product_catalog(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(product_catalog)").fetchall()}
    if {"product_code", "name", "category", "sku", "price", "sales_30d", "rating"} & columns:
        _rebuild_product_catalog(conn, columns)
        return

    additions = {
        "sku_id": "TEXT",
        "product_name": "TEXT NOT NULL DEFAULT ''",
        "category_l1": "TEXT NOT NULL DEFAULT ''",
        "category_l2": "TEXT NOT NULL DEFAULT ''",
        "pricing_model": "TEXT NOT NULL DEFAULT 'fixed'",
        "weight_g": "REAL",
        "purity": "TEXT NOT NULL DEFAULT ''",
        "gem_carat": "REAL",
        "gem_color": "TEXT",
        "gem_clarity": "TEXT",
        "gem_cut": "TEXT",
        "tag_price_rmb": "REAL NOT NULL DEFAULT 0",
        "list_price_rmb": "REAL NOT NULL DEFAULT 0",
        "last_30d_min_price": "REAL NOT NULL DEFAULT 0",
        "last_90d_min_price": "REAL NOT NULL DEFAULT 0",
        "last_365d_min_price": "REAL NOT NULL DEFAULT 0",
        "last_90d_sales": "INTEGER NOT NULL DEFAULT 0",
        "review_rate": "REAL NOT NULL DEFAULT 0",
        "return_rate": "REAL NOT NULL DEFAULT 0",
        "new_product": "INTEGER NOT NULL DEFAULT 0",
        "certificate_ids_json": "TEXT NOT NULL DEFAULT '[]'",
        "factory_id": "TEXT NOT NULL DEFAULT ''",
        "lead_time_days": "INTEGER NOT NULL DEFAULT 0",
        "active_campaigns_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for column, definition in additions.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE product_catalog ADD COLUMN {column} {definition}")


def _text_expr(columns: set[str], names: tuple[str, ...], default: str = "") -> str:
    parts = [f"NULLIF({name}, '')" for name in names if name in columns]
    escaped = default.replace("'", "''")
    if not parts:
        return f"'{escaped}'"
    parts.append(f"'{escaped}'")
    return f"COALESCE({', '.join(parts)})"


def _number_expr(columns: set[str], names: tuple[str, ...], default: Any = 0) -> str:
    parts = [name for name in names if name in columns]
    if not parts:
        return str(default)
    parts.append(str(default))
    return f"COALESCE({', '.join(parts)})"


def _rebuild_product_catalog(conn: sqlite3.Connection, columns: set[str]) -> None:
    conn.execute("DROP TABLE IF EXISTS product_catalog_new")
    conn.execute(
        """
        CREATE TABLE product_catalog_new (
            id TEXT PRIMARY KEY,
            sku_id TEXT NOT NULL UNIQUE,
            product_name TEXT NOT NULL,
            brand TEXT NOT NULL DEFAULT '',
            category_l1 TEXT NOT NULL DEFAULT '',
            category_l2 TEXT NOT NULL DEFAULT '',
            pricing_model TEXT NOT NULL DEFAULT 'fixed',
            weight_g REAL,
            purity TEXT NOT NULL DEFAULT '',
            gem_carat REAL,
            gem_color TEXT,
            gem_clarity TEXT,
            gem_cut TEXT,
            tag_price_rmb REAL NOT NULL DEFAULT 0,
            list_price_rmb REAL NOT NULL DEFAULT 0,
            last_30d_min_price REAL NOT NULL DEFAULT 0,
            last_90d_min_price REAL NOT NULL DEFAULT 0,
            last_365d_min_price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            last_90d_sales INTEGER NOT NULL DEFAULT 0,
            review_rate REAL NOT NULL DEFAULT 0,
            return_rate REAL NOT NULL DEFAULT 0,
            new_product INTEGER NOT NULL DEFAULT 0,
            certificate_ids_json TEXT NOT NULL DEFAULT '[]',
            factory_id TEXT NOT NULL DEFAULT '',
            lead_time_days INTEGER NOT NULL DEFAULT 0,
            active_campaigns_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT '在售',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    sku_parts = [f"NULLIF({name}, '')" for name in ("sku_id", "product_code") if name in columns]
    sku_parts.append("'SKU' || printf('%06d', rowid)")
    sku_expr = f"COALESCE({', '.join(sku_parts)})"
    conn.execute(
        f"""
        INSERT INTO product_catalog_new (
            id, sku_id, product_name, brand, category_l1, category_l2,
            pricing_model, weight_g, purity, gem_carat, gem_color,
            gem_clarity, gem_cut, tag_price_rmb, list_price_rmb,
            last_30d_min_price, last_90d_min_price, last_365d_min_price,
            stock, last_90d_sales, review_rate, return_rate, new_product,
            certificate_ids_json, factory_id, lead_time_days,
            active_campaigns_json, status, notes, created_at, updated_at
        )
        SELECT
            {_text_expr(columns, ('id',), '')},
            {sku_expr},
            {_text_expr(columns, ('product_name', 'name'), '未命名商品')},
            {_text_expr(columns, ('brand',), '')},
            {_text_expr(columns, ('category_l1', 'category'), '')},
            {_text_expr(columns, ('category_l2',), '')},
            {_text_expr(columns, ('pricing_model',), 'fixed')},
            {_number_expr(columns, ('weight_g',), 'NULL')},
            {_text_expr(columns, ('purity',), '')},
            {_number_expr(columns, ('gem_carat',), 'NULL')},
            {_text_expr(columns, ('gem_color',), '')},
            {_text_expr(columns, ('gem_clarity',), '')},
            {_text_expr(columns, ('gem_cut',), '')},
            {_number_expr(columns, ('tag_price_rmb', 'price'), 0)},
            {_number_expr(columns, ('list_price_rmb', 'price'), 0)},
            {_number_expr(columns, ('last_30d_min_price',), 0)},
            {_number_expr(columns, ('last_90d_min_price',), 0)},
            {_number_expr(columns, ('last_365d_min_price',), 0)},
            {_number_expr(columns, ('stock',), 0)},
            {_number_expr(columns, ('last_90d_sales', 'sales_30d'), 0)},
            {_number_expr(columns, ('review_rate', 'rating'), 0)},
            {_number_expr(columns, ('return_rate',), 0)},
            {_number_expr(columns, ('new_product',), 0)},
            {_text_expr(columns, ('certificate_ids_json',), '[]')},
            {_text_expr(columns, ('factory_id',), '')},
            {_number_expr(columns, ('lead_time_days',), 0)},
            {_text_expr(columns, ('active_campaigns_json',), '[]')},
            {_text_expr(columns, ('status',), '在售')},
            {_text_expr(columns, ('notes',), '')},
            {_text_expr(columns, ('created_at',), '')},
            {_text_expr(columns, ('updated_at',), '')}
        FROM product_catalog
        """
    )
    conn.execute("DROP TABLE product_catalog")
    conn.execute("ALTER TABLE product_catalog_new RENAME TO product_catalog")


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


def _next_sku_id(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT sku_id
        FROM product_catalog
        WHERE sku_id LIKE 'SKU%'
        ORDER BY sku_id DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return "SKU000001"
    try:
        number = int(str(row["sku_id"])[3:]) + 1
    except ValueError:
        number = 1
    return f"SKU{number:06d}"


def _catalog_payload(data: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(data.get("product_name") or data.get("name") or "未命名商品").strip()[:160],
        str(data.get("brand") or "").strip(),
        str(data.get("category_l1") or data.get("category") or "").strip(),
        str(data.get("category_l2") or "").strip(),
        str(data.get("pricing_model") or "fixed").strip(),
        data.get("weight_g"),
        str(data.get("purity") or "").strip(),
        data.get("gem_carat"),
        data.get("gem_color"),
        data.get("gem_clarity"),
        data.get("gem_cut"),
        float(data.get("tag_price_rmb") or data.get("price") or 0),
        float(data.get("list_price_rmb") or data.get("price") or 0),
        float(data.get("last_30d_min_price") or 0),
        float(data.get("last_90d_min_price") or 0),
        float(data.get("last_365d_min_price") or 0),
        int(data.get("stock") or 0),
        int(data.get("last_90d_sales") or data.get("sales_30d") or 0),
        float(data.get("review_rate") or data.get("rating") or 0),
        float(data.get("return_rate") or 0),
        1 if data.get("new_product") else 0,
        _json(data.get("certificate_ids") or []),
        str(data.get("factory_id") or "").strip(),
        int(data.get("lead_time_days") or 0),
        _json(data.get("active_campaigns") or []),
        str(data.get("status") or "在售").strip(),
        str(data.get("notes") or "").strip(),
    )


def _catalog_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["certificate_ids"] = json.loads(item.get("certificate_ids_json") or "[]")
    item["active_campaigns"] = json.loads(item.get("active_campaigns_json") or "[]")
    item["new_product"] = bool(item.get("new_product"))
    item["product_code"] = item.get("sku_id", "")
    item["name"] = item.get("product_name", "")
    item["category"] = item.get("category_l1", "")
    item["price"] = item.get("list_price_rmb", 0)
    item["sales_30d"] = item.get("last_90d_sales", 0)
    item["rating"] = item.get("review_rate", 0)
    return item


def create_catalog_product(data: dict[str, Any]) -> str:
    init_db()
    product_id = str(uuid.uuid4())
    with connect() as conn:
        sku_id = data.get("sku_id") or _next_sku_id(conn)
        conn.execute(
            """
            INSERT INTO product_catalog (
                id, sku_id, product_name, brand, category_l1, category_l2,
                pricing_model, weight_g, purity, gem_carat, gem_color,
                gem_clarity, gem_cut, tag_price_rmb, list_price_rmb,
                last_30d_min_price, last_90d_min_price, last_365d_min_price,
                stock, last_90d_sales, review_rate, return_rate, new_product,
                certificate_ids_json, factory_id, lead_time_days,
                active_campaigns_json, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (product_id, sku_id, *_catalog_payload(data)),
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
                WHERE sku_id LIKE ?
                   OR product_name LIKE ?
                   OR category_l1 LIKE ?
                   OR category_l2 LIKE ?
                   OR brand LIKE ?
                   OR purity LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (q, q, q, q, q, q, limit),
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
    return [_catalog_row(row) for row in rows]


def get_catalog_product(product_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM product_catalog WHERE id = ?", (product_id,)).fetchone()
    return _catalog_row(row) if row else None


def update_catalog_product(product_id: str, data: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE product_catalog
            SET product_name = ?, brand = ?, category_l1 = ?, category_l2 = ?,
                pricing_model = ?, weight_g = ?, purity = ?, gem_carat = ?,
                gem_color = ?, gem_clarity = ?, gem_cut = ?,
                tag_price_rmb = ?, list_price_rmb = ?, last_30d_min_price = ?,
                last_90d_min_price = ?, last_365d_min_price = ?, stock = ?,
                last_90d_sales = ?, review_rate = ?, return_rate = ?,
                new_product = ?, certificate_ids_json = ?, factory_id = ?,
                lead_time_days = ?, active_campaigns_json = ?, status = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (*_catalog_payload(data), product_id),
        )


def delete_catalog_product(product_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM product_catalog WHERE id = ?", (product_id,))


SAMPLE_CATALOG_PRODUCTS: list[dict[str, Any]] = [
    {"sku_id": "SKU000001", "product_name": "足金999古法云纹手镯25g", "brand": "云璟珠宝", "category_l1": "黄金", "category_l2": "古法金", "pricing_model": "weight", "weight_g": 25.0, "purity": "999", "tag_price_rmb": 19800, "list_price_rmb": 18800, "last_30d_min_price": 18200, "last_90d_min_price": 17800, "last_365d_min_price": 16500, "stock": 320, "last_90d_sales": 158, "review_rate": 98.5, "return_rate": 1.2, "new_product": False, "certificate_ids": ["CERT-GD-0001"], "factory_id": "F-SZ-001", "lead_time_days": 14, "active_campaigns": ["tmall:2025_618"], "status": "在售"},
    {"sku_id": "SKU000002", "product_name": "足金999福字吊坠3.5g", "brand": "星禾金作", "category_l1": "黄金", "category_l2": "足金", "pricing_model": "weight", "weight_g": 3.5, "purity": "999", "tag_price_rmb": 2880, "list_price_rmb": 2680, "last_30d_min_price": 2580, "last_90d_min_price": 2480, "last_365d_min_price": 2350, "stock": 1800, "last_90d_sales": 1024, "review_rate": 97.8, "return_rate": 2.5, "new_product": False, "certificate_ids": ["CERT-GD-0002"], "factory_id": "F-SZ-002", "lead_time_days": 10, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000003", "product_name": "足金999.9婚嫁三件套18g", "brand": "禾光珠宝", "category_l1": "黄金", "category_l2": "千足金", "pricing_model": "weight", "weight_g": 18.0, "purity": "999.9", "tag_price_rmb": 14800, "list_price_rmb": 14000, "last_30d_min_price": 13500, "last_90d_min_price": 13200, "last_365d_min_price": 12800, "stock": 280, "last_90d_sales": 95, "review_rate": 98.0, "return_rate": 1.8, "new_product": False, "certificate_ids": ["CERT-GD-0003"], "factory_id": "F-SZ-001", "lead_time_days": 18, "active_campaigns": ["tmall:2025_brandday"], "status": "在售"},
    {"sku_id": "SKU000004", "product_name": "足金999婴儿手镯5.5g", "brand": "云璟珠宝", "category_l1": "黄金", "category_l2": "足金", "pricing_model": "weight", "weight_g": 5.5, "purity": "999", "tag_price_rmb": 4380, "list_price_rmb": 4180, "last_30d_min_price": 4080, "last_90d_min_price": 3980, "last_365d_min_price": 3850, "stock": 600, "last_90d_sales": 312, "review_rate": 99.0, "return_rate": 0.5, "new_product": False, "certificate_ids": ["CERT-GD-0004"], "factory_id": "F-SZ-002", "lead_time_days": 12, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000005", "product_name": "万足金999.99投资金条50g", "brand": "珑曜金业", "category_l1": "黄金", "category_l2": "万足金", "pricing_model": "weight", "weight_g": 50.0, "purity": "999.99", "tag_price_rmb": 38800, "list_price_rmb": 0, "last_30d_min_price": 0, "last_90d_min_price": 0, "last_365d_min_price": 0, "stock": 120, "last_90d_sales": 45, "review_rate": 99.5, "return_rate": 0.2, "new_product": False, "certificate_ids": ["CERT-AU-0005"], "factory_id": "F-SH-003", "lead_time_days": 20, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000006", "product_name": "5G黄金小蛮腰耳钉1.2g", "brand": "星禾金作", "category_l1": "黄金", "category_l2": "5G黄金", "pricing_model": "fixed", "weight_g": 1.2, "purity": "999", "tag_price_rmb": 1380, "list_price_rmb": 1280, "last_30d_min_price": 1180, "last_90d_min_price": 1080, "last_365d_min_price": 980, "stock": 2400, "last_90d_sales": 1850, "review_rate": 98.2, "return_rate": 1.5, "new_product": True, "certificate_ids": ["CERT-GD-0006"], "factory_id": "F-SZ-002", "lead_time_days": 9, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000007", "product_name": "5G黄金转运珠手链2.8g", "brand": "星禾金作", "category_l1": "黄金", "category_l2": "5G黄金", "pricing_model": "fixed", "weight_g": 2.8, "purity": "999", "tag_price_rmb": 2680, "list_price_rmb": 2480, "last_30d_min_price": 2380, "last_90d_min_price": 2280, "last_365d_min_price": 2180, "stock": 1800, "last_90d_sales": 920, "review_rate": 97.5, "return_rate": 2.8, "new_product": True, "certificate_ids": ["CERT-GD-0007"], "factory_id": "F-SZ-002", "lead_time_days": 9, "active_campaigns": ["tmall:2025_618"], "status": "在售"},
    {"sku_id": "SKU000008", "product_name": "硬足金福字吊坠1.5g", "brand": "禾光珠宝", "category_l1": "黄金", "category_l2": "硬足金", "pricing_model": "fixed", "weight_g": 1.5, "purity": "999", "tag_price_rmb": 1580, "list_price_rmb": 1480, "last_30d_min_price": 1380, "last_90d_min_price": 1280, "last_365d_min_price": 1180, "stock": 1500, "last_90d_sales": 780, "review_rate": 98.8, "return_rate": 1.1, "new_product": False, "certificate_ids": ["CERT-GD-0008"], "factory_id": "F-SZ-002", "lead_time_days": 10, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000009", "product_name": "古法金传承福手镯22g", "brand": "云璟珠宝", "category_l1": "黄金", "category_l2": "古法金", "pricing_model": "fixed", "weight_g": 22.0, "purity": "999", "tag_price_rmb": 23800, "list_price_rmb": 22800, "last_30d_min_price": 22000, "last_90d_min_price": 21500, "last_365d_min_price": 20800, "stock": 220, "last_90d_sales": 75, "review_rate": 99.1, "return_rate": 0.8, "new_product": True, "certificate_ids": ["CERT-GD-0009"], "factory_id": "F-SZ-001", "lead_time_days": 18, "active_campaigns": ["tmall:2025_brandday"], "status": "在售"},
    {"sku_id": "SKU000010", "product_name": "18K金钻石项链0.50ct", "brand": "璟澜珠宝", "category_l1": "镶嵌", "category_l2": "K金", "pricing_model": "fixed", "weight_g": 6.5, "purity": "Au750", "gem_carat": 0.5, "gem_color": "F", "gem_clarity": "VS1", "gem_cut": "EX", "tag_price_rmb": 28800, "list_price_rmb": 27800, "last_30d_min_price": 26800, "last_90d_min_price": 26000, "last_365d_min_price": 25500, "stock": 60, "last_90d_sales": 32, "review_rate": 98.0, "return_rate": 2.0, "new_product": False, "certificate_ids": ["CERT-DM-0010"], "factory_id": "F-SH-002", "lead_time_days": 25, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000011", "product_name": "18K金钻石项链0.30ct", "brand": "璟澜珠宝", "category_l1": "镶嵌", "category_l2": "K金", "pricing_model": "fixed", "weight_g": 5.2, "purity": "Au750", "gem_carat": 0.3, "gem_color": "G", "gem_clarity": "VS2", "gem_cut": "EX", "tag_price_rmb": 18800, "list_price_rmb": 17800, "last_30d_min_price": 16800, "last_90d_min_price": 16000, "last_365d_min_price": 15500, "stock": 80, "last_90d_sales": 48, "review_rate": 97.8, "return_rate": 1.8, "new_product": False, "certificate_ids": ["CERT-DM-0011"], "factory_id": "F-SH-002", "lead_time_days": 25, "active_campaigns": ["tmall:2025_brandday"], "status": "在售"},
    {"sku_id": "SKU000012", "product_name": "18K金钻戒0.20ct", "brand": "星诺婚饰", "category_l1": "镶嵌", "category_l2": "求婚钻戒", "pricing_model": "fixed", "weight_g": 3.5, "purity": "Au750", "gem_carat": 0.2, "gem_color": "H", "gem_clarity": "SI1", "gem_cut": "VG", "tag_price_rmb": 9880, "list_price_rmb": 9380, "last_30d_min_price": 8980, "last_90d_min_price": 8780, "last_365d_min_price": 8580, "stock": 150, "last_90d_sales": 96, "review_rate": 98.2, "return_rate": 1.5, "new_product": True, "certificate_ids": ["CERT-DM-0012"], "factory_id": "F-SH-002", "lead_time_days": 22, "active_campaigns": ["jd:2025_brandday"], "status": "在售"},
    {"sku_id": "SKU000013", "product_name": "星芒30分钻戒", "brand": "曜石切工", "category_l1": "镶嵌", "category_l2": "求婚钻戒", "pricing_model": "fixed", "weight_g": 3.8, "purity": "Au750", "gem_carat": 0.3, "gem_color": "F", "gem_clarity": "VVS2", "gem_cut": "EX", "tag_price_rmb": 22800, "list_price_rmb": 21800, "last_30d_min_price": 20800, "last_90d_min_price": 20200, "last_365d_min_price": 19800, "stock": 80, "last_90d_sales": 52, "review_rate": 99.0, "return_rate": 1.0, "new_product": True, "certificate_ids": ["CERT-DM-0013"], "factory_id": "F-SH-002", "lead_time_days": 24, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000014", "product_name": "铂金Pt950 50分钻戒", "brand": "星诺婚饰", "category_l1": "镶嵌", "category_l2": "求婚钻戒", "pricing_model": "fixed", "weight_g": 4.2, "purity": "Pt950", "gem_carat": 0.5, "gem_color": "E", "gem_clarity": "VVS1", "gem_cut": "EX", "tag_price_rmb": 38800, "list_price_rmb": 36800, "last_30d_min_price": 35800, "last_90d_min_price": 34800, "last_365d_min_price": 33800, "stock": 40, "last_90d_sales": 18, "review_rate": 98.5, "return_rate": 1.2, "new_product": False, "certificate_ids": ["CERT-DM-0014"], "factory_id": "F-SH-002", "lead_time_days": 28, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000015", "product_name": "18K金钻石耳钉0.10ct一对", "brand": "璟澜珠宝", "category_l1": "镶嵌", "category_l2": "耳饰", "pricing_model": "fixed", "weight_g": 1.8, "purity": "Au750", "gem_carat": 0.1, "gem_color": "G", "gem_clarity": "VS2", "gem_cut": "EX", "tag_price_rmb": 4880, "list_price_rmb": 4680, "last_30d_min_price": 4480, "last_90d_min_price": 4280, "last_365d_min_price": 4180, "stock": 320, "last_90d_sales": 195, "review_rate": 98.0, "return_rate": 1.8, "new_product": False, "certificate_ids": ["CERT-DM-0015"], "factory_id": "F-SH-002", "lead_time_days": 20, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000016", "product_name": "翡翠A货平安无事牌吊坠", "brand": "翠岚坊", "category_l1": "玉石", "category_l2": "翡翠", "pricing_model": "fixed", "purity": "A货", "tag_price_rmb": 18800, "list_price_rmb": 17800, "last_30d_min_price": 17000, "last_90d_min_price": 16500, "last_365d_min_price": 16000, "stock": 30, "last_90d_sales": 12, "review_rate": 97.0, "return_rate": 3.5, "new_product": False, "certificate_ids": ["CERT-JD-0016"], "factory_id": "F-GZ-001", "lead_time_days": 30, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000017", "product_name": "翡翠A货福豆挂坠", "brand": "翠岚坊", "category_l1": "玉石", "category_l2": "翡翠", "pricing_model": "fixed", "purity": "A货", "tag_price_rmb": 5880, "list_price_rmb": 5580, "last_30d_min_price": 5380, "last_90d_min_price": 5180, "last_365d_min_price": 4980, "stock": 80, "last_90d_sales": 38, "review_rate": 97.5, "return_rate": 2.8, "new_product": True, "certificate_ids": ["CERT-JD-0017"], "factory_id": "F-GZ-001", "lead_time_days": 30, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000018", "product_name": "Akoya海水珍珠项链7-8mm", "brand": "月汐珍珠", "category_l1": "珍珠", "category_l2": "海水珍珠", "pricing_model": "fixed", "tag_price_rmb": 6880, "list_price_rmb": 6580, "last_30d_min_price": 6280, "last_90d_min_price": 6080, "last_365d_min_price": 5880, "stock": 120, "last_90d_sales": 65, "review_rate": 98.0, "return_rate": 2.0, "new_product": False, "certificate_ids": ["CERT-PR-0018"], "factory_id": "F-SH-004", "lead_time_days": 21, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000019", "product_name": "铂金Pt950项链5.5g", "brand": "铂映工坊", "category_l1": "铂金", "category_l2": "项链", "pricing_model": "weight", "weight_g": 5.5, "purity": "Pt950", "tag_price_rmb": 5680, "list_price_rmb": 5380, "last_30d_min_price": 5180, "last_90d_min_price": 4980, "last_365d_min_price": 4780, "stock": 240, "last_90d_sales": 132, "review_rate": 98.2, "return_rate": 1.8, "new_product": False, "certificate_ids": ["CERT-PT-0019"], "factory_id": "F-SH-001", "lead_time_days": 18, "active_campaigns": [], "status": "在售"},
    {"sku_id": "SKU000020", "product_name": "925银转运珠手链", "brand": "银澈饰品", "category_l1": "银饰", "category_l2": "手链", "pricing_model": "fixed", "weight_g": 4.5, "purity": "925", "tag_price_rmb": 580, "list_price_rmb": 480, "last_30d_min_price": 380, "last_90d_min_price": 350, "last_365d_min_price": 320, "stock": 1500, "last_90d_sales": 880, "review_rate": 97.5, "return_rate": 3.0, "new_product": True, "certificate_ids": ["CERT-SV-0020"], "factory_id": "F-SZ-003", "lead_time_days": 12, "active_campaigns": [], "status": "在售"},
]


def seed_sample_catalog(force: bool = False) -> int:
    init_db()
    with connect() as conn:
        if force:
            conn.execute("DELETE FROM product_catalog")
        existing = conn.execute("SELECT COUNT(*) AS count FROM product_catalog").fetchone()["count"]
        if existing and not force:
            return 0
    count = 0
    for item in SAMPLE_CATALOG_PRODUCTS:
        create_catalog_product(item)
        count += 1
    return count


def create_knowledge_base(
    name: str,
    description: str = "",
    kb_type: str = "personal",
    file_type: str = "mixed",
    index_path: str = "",
    embedding_backend: str = "",
    knowledge_id: str | None = None,
) -> str:
    init_db()
    kb_id = knowledge_id or f"kb_{uuid.uuid4().hex[:12]}"
    clean_name = (name or "未命名知识库").strip()[:160] or "未命名知识库"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO knowledge_bases (
                id, name, description, type, index_path,
                file_count, chunk_count, file_type, embedding_backend
            )
            VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (
                kb_id,
                clean_name,
                description.strip(),
                kb_type.strip() or "personal",
                index_path,
                file_type.strip() or "mixed",
                embedding_backend.strip(),
            ),
        )
    return kb_id


def get_knowledge_base(knowledge_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, description, type, index_path, file_count,
                   chunk_count, file_type, embedding_backend, created_at, updated_at
            FROM knowledge_bases
            WHERE id = ?
            """,
            (knowledge_id,),
        ).fetchone()
    return dict(row) if row else None


def list_knowledge_bases(kb_type: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        if kb_type:
            rows = conn.execute(
                """
                SELECT id, name, description, type, index_path, file_count,
                       chunk_count, file_type, embedding_backend, created_at, updated_at
                FROM knowledge_bases
                WHERE type = ?
                ORDER BY updated_at DESC
                """,
                (kb_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, description, type, index_path, file_count,
                       chunk_count, file_type, embedding_backend, created_at, updated_at
                FROM knowledge_bases
                ORDER BY updated_at DESC
                """
            ).fetchall()
    return [dict(row) for row in rows]


def update_knowledge_base_stats(
    knowledge_id: str,
    *,
    file_count: int | None = None,
    chunk_count: int | None = None,
    file_type: str | None = None,
    embedding_backend: str | None = None,
    index_path: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> None:
    assignments: list[str] = []
    values: list[Any] = []
    if file_count is not None:
        assignments.append("file_count = ?")
        values.append(int(file_count))
    if chunk_count is not None:
        assignments.append("chunk_count = ?")
        values.append(int(chunk_count))
    if file_type is not None:
        assignments.append("file_type = ?")
        values.append(file_type)
    if embedding_backend is not None:
        assignments.append("embedding_backend = ?")
        values.append(embedding_backend)
    if index_path is not None:
        assignments.append("index_path = ?")
        values.append(index_path)
    if name is not None:
        assignments.append("name = ?")
        values.append(name.strip()[:160] or "未命名知识库")
    if description is not None:
        assignments.append("description = ?")
        values.append(description.strip())
    if not assignments:
        return
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(knowledge_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE knowledge_bases SET {', '.join(assignments)} WHERE id = ?",
            values,
        )


def delete_knowledge_base(knowledge_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM knowledge_bases WHERE id = ?", (knowledge_id,))


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
