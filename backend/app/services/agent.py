"""Agent service - orchestrates rule parsing with knowledge base context."""
import uuid
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..core.config import DATA_DIR
from .llm import stream_chat


# In-memory storage (will be replaced by database later)
_tasks: dict[str, dict] = {}
_knowledge_bases: dict[str, dict] = {}
_projects: dict[str, dict] = {}

# Official knowledge bases (pre-loaded)
_official_kb = {
    "official_tmall618": {
        "id": "official_tmall618",
        "name": "天猫618大促选品规则",
        "type": "official",
        "description": "天猫618大促活动选品标准规则模板",
        "content": """天猫618大促选品规则
1. 参与商品必须满足：近30天销量≥100件；好评率≥95%；库存≥500件。
2. 价格要求：活动价不得高于近30天最低价；折扣力度≥7折。
3. 品类限制：黄金类自单店最多5个SKU；钻石类自单店最多10个SKU。
4. 互斥规则：已参加"品牌日"活动的商品不可重复报名。""",
    },
    "official_jd1111": {
        "id": "official_jd1111",
        "name": "京东双11活动规则",
        "type": "official",
        "description": "京东双11大促活动通用规则模板",
        "content": """京东双11大促活动规则
1. 店铺评分要求：DSR≥4.8分，开店时间≥90天。
2. 商品要求：近30天销量≥50件，好评率≥90%。
3. 价格保护：活动前15天为价格保护期，不得先涨后降。
4. 库存锁定：报名成功后库存锁定，活动期间不可修改。
5. 发货时效：活动订单48小时内发货，超时赔付。""",
    },
    "official_pdd_promo": {
        "id": "official_pdd_promo",
        "name": "拼多多百亿补贴规则",
        "type": "official",
        "description": "拼多多百亿补贴活动通用规则",
        "content": """拼多多百亿补贴活动规则
1. 商品需为品牌正品，需提供品牌授权证明。
2. 价格需为全网最低价的85折及以下。
3. 单SKU库存≥1000件。
4. 活动期间不可下架或修改价格。
5. 需缴纳保证金5000元。""",
    },
}


def _load_tasks_file() -> dict:
    """Load tasks from JSON file."""
    tasks_file = DATA_DIR / "tasks.json"
    if tasks_file.exists():
        with open(tasks_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_tasks_file():
    """Save tasks to JSON file."""
    tasks_file = DATA_DIR / "tasks.json"
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump(_tasks, f, ensure_ascii=False, indent=2)


def _load_knowledge_file() -> dict:
    """Load knowledge bases from JSON file."""
    kb_file = DATA_DIR / "knowledge.json"
    if kb_file.exists():
        with open(kb_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_knowledge_file():
    """Save knowledge bases to JSON file."""
    kb_file = DATA_DIR / "knowledge.json"
    with open(kb_file, "w", encoding="utf-8") as f:
        json.dump(_knowledge_bases, f, ensure_ascii=False, indent=2)


def _load_projects_file() -> dict:
    """Load projects from JSON file."""
    pf = DATA_DIR / "projects.json"
    if pf.exists():
        with open(pf, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_projects_file():
    """Save projects to JSON file."""
    pf = DATA_DIR / "projects.json"
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(_projects, f, ensure_ascii=False, indent=2)


# Initialize from files
_tasks = _load_tasks_file()
_knowledge_bases = _load_knowledge_file()
_projects = _load_projects_file()

# Ensure a default project exists
if not _projects:
    pid = "default"
    _projects[pid] = {"id": pid, "name": "默认项目", "created_at": datetime.now().isoformat()}
    _save_projects_file()


def create_task(project_id: str = "default") -> dict:
    """Create a new task/session within a project."""
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    task = {
        "task_id": task_id,
        "title": "新任务",
        "created_at": now,
        "messages": [],
        "project_id": project_id,
    }
    _tasks[task_id] = task
    _save_tasks_file()
    return {"task_id": task_id, "created_at": now, "project_id": project_id}


def get_task(task_id: str) -> Optional[dict]:
    """Get a task by ID."""
    return _tasks.get(task_id)


def add_message(task_id: str, role: str, content: str, metadata: dict | None = None) -> bool:
    """Add a message to a task."""
    task = _tasks.get(task_id)
    if not task:
        return False

    msg = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        msg["metadata"] = metadata

    task["messages"].append(msg)

    # Auto-update title from first user message
    if role == "user" and len(task["messages"]) == 1:
        task["title"] = content[:30] + ("..." if len(content) > 30 else "")

    _save_tasks_file()
    return True


def get_history() -> list[dict]:
    """Get all tasks as history list, sorted by created_at desc."""
    items = []
    for task_id, task in _tasks.items():
        items.append({
            "task_id": task_id,
            "title": task.get("title", "未命名"),
            "created_at": task["created_at"],
            "message_count": len(task["messages"]),
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


def get_history_detail(task_id: str) -> Optional[dict]:
    """Get detailed history for a task."""
    task = _tasks.get(task_id)
    if not task:
        return None
    return {
        "task_id": task["task_id"],
        "title": task.get("title", "未命名"),
        "created_at": task["created_at"],
        "messages": task["messages"],
    }


def delete_task(task_id: str) -> bool:
    """Delete a task and its history."""
    if task_id in _tasks:
        del _tasks[task_id]
        _save_tasks_file()
        return True
    return False


def rename_task(task_id: str, new_name: str) -> bool:
    """Rename a task."""
    task = _tasks.get(task_id)
    if not task:
        return False
    task["title"] = new_name
    _save_tasks_file()
    return True


def get_official_knowledge() -> list[dict]:
    """Get official knowledge base list."""
    return [
        {
            "id": kb["id"],
            "name": kb["name"],
            "type": kb["type"],
            "description": kb["description"],
        }
        for kb in _official_kb.values()
    ]


def get_personal_knowledge() -> list[dict]:
    """Get personal knowledge base list."""
    return [
        {
            "id": kb_id,
            "name": kb["name"],
            "type": "personal",
            "description": kb.get("description", ""),
            "created_at": kb.get("created_at", ""),
            "file_type": kb.get("file_type", ""),
        }
        for kb_id, kb in _knowledge_bases.items()
    ]


def upload_knowledge(name: str, content: str, file_type: str = "text") -> dict:
    """Upload a new personal knowledge base."""
    kb_id = f"kb_{uuid.uuid4().hex[:12]}"
    kb = {
        "id": kb_id,
        "name": name,
        "type": "personal",
        "description": f"用户上传的知识库 ({file_type})",
        "content": content,
        "file_type": file_type,
        "created_at": datetime.now().isoformat(),
    }
    _knowledge_bases[kb_id] = kb
    _save_knowledge_file()
    return {"id": kb_id, "name": name, "message": "知识库上传成功"}


def delete_knowledge(kb_id: str) -> bool:
    """Delete a personal knowledge base."""
    if kb_id in _knowledge_bases:
        del _knowledge_bases[kb_id]
        _save_knowledge_file()
        return True
    return False


def get_knowledge_content(kb_id: str) -> str:
    """Get knowledge base content. Checks both official and personal."""
    if kb_id in _official_kb:
        return _official_kb[kb_id]["content"]
    kb = _knowledge_bases.get(kb_id)
    if kb:
        return kb.get("content", "")
    return ""


# --- Project management ---

def create_project(name: str) -> dict:
    """Create a new project folder."""
    pid = f"proj_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    proj = {"id": pid, "name": name, "created_at": now}
    _projects[pid] = proj
    _save_projects_file()
    return proj


def get_projects() -> list[dict]:
    """Get all projects."""
    return sorted(_projects.values(), key=lambda p: p["created_at"])


def rename_project(project_id: str, new_name: str) -> bool:
    """Rename a project."""
    proj = _projects.get(project_id)
    if not proj:
        return False
    proj["name"] = new_name
    _save_projects_file()
    return True


def get_history(project_id: str | None = None) -> list[dict]:
    """Get tasks as history list, optionally filtered by project."""
    items = []
    for task_id, task in _tasks.items():
        if project_id and task.get("project_id", "default") != project_id:
            continue
        items.append({
            "task_id": task_id,
            "title": task.get("title", "未命名"),
            "created_at": task["created_at"],
            "message_count": len(task["messages"]),
            "project_id": task.get("project_id", "default"),
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items
