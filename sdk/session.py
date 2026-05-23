from __future__ import annotations

import json
import time
from pathlib import Path

from sdk.config import SDKConfig


class SessionManager:
    def __init__(self, config: SDKConfig | None = None):
        self.config = config or SDKConfig()
        self._base_dir = Path(self.config.SESSION_DIR)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self._base_dir / f"{safe_id}.json"

    async def get(self, session_id: str) -> dict | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("_updated_at", 0) > self.config.SESSION_TTL:
            path.unlink(missing_ok=True)
            return None
        return data

    async def save(self, session_id: str, state: dict):
        state["_updated_at"] = time.time()
        path = self._path(session_id)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def delete(self, session_id: str):
        self._path(session_id).unlink(missing_ok=True)

    async def list_sessions(self) -> list[str]:
        sessions = []
        for p in self._base_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if time.time() - data.get("_updated_at", 0) <= self.config.SESSION_TTL:
                    sessions.append(p.stem)
            except (json.JSONDecodeError, OSError):
                continue
        return sessions
