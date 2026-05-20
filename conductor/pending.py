from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


class PendingStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, chat_id: int, payload: dict[str, Any], questions: list[str]) -> str:
        data = self._load()
        pending_id = uuid.uuid4().hex[:10]
        data[pending_id] = {"chat_id": chat_id, "payload": payload, "questions": questions}
        self._save(data)
        return pending_id

    def list_for_chat(self, chat_id: int) -> dict[str, Any]:
        return {key: value for key, value in self._load().items() if value.get("chat_id") == chat_id}

    def pop_oldest_for_chat(self, chat_id: int) -> tuple[str, dict[str, Any]] | None:
        data = self._load()
        for key, value in data.items():
            if value.get("chat_id") == chat_id:
                item = data.pop(key)
                self._save(data)
                return key, item
        return None

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
