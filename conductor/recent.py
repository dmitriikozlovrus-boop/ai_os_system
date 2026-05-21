from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RecentStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, chat_id: int, payload: dict[str, Any]) -> None:
        data = self._load()
        data[str(chat_id)] = payload
        self._save(data)

    def get(self, chat_id: int) -> dict[str, Any] | None:
        return self._load().get(str(chat_id))

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
