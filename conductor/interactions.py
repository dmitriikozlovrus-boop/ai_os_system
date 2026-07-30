from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class InteractionStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        chat_id: int,
        *,
        text: str,
        telegram_message_id: int | None = None,
        reply_to_message_id: int | None = None,
        model: str = "",
        status: str = "started",
    ) -> str:
        data = self._load()
        interaction_id = uuid.uuid4().hex[:12]
        data[interaction_id] = {
            "interaction_id": interaction_id,
            "chat_id": chat_id,
            "telegram_message_id": telegram_message_id,
            "reply_to_message_id": reply_to_message_id,
            "input_text": text,
            "classification": None,
            "pending": [],
            "questions": [],
            "created": {"tasks": [], "studies": [], "goods": []},
            "errors": [],
            "bot_messages": [],
            "bot_message_ids": [],
            "model": model,
            "timestamp": _now(),
            "status": status,
        }
        self._save(data)
        return interaction_id

    def update(self, interaction_id: str | None, **fields: Any) -> None:
        if not interaction_id:
            return
        data = self._load()
        if interaction_id not in data:
            return
        data[interaction_id].update(fields)
        data[interaction_id]["timestamp"] = _now()
        self._save(data)

    def append(self, interaction_id: str | None, field: str, value: Any) -> None:
        if not interaction_id:
            return
        data = self._load()
        if interaction_id not in data:
            return
        data[interaction_id].setdefault(field, [])
        data[interaction_id][field].append(value)
        data[interaction_id]["timestamp"] = _now()
        self._save(data)

    def latest_for_chat(self, chat_id: int) -> dict[str, Any] | None:
        items = [item for item in self._load().values() if item.get("chat_id") == chat_id]
        return max(items, key=lambda item: item.get("timestamp", "")) if items else None

    def find_by_reply(self, chat_id: int, reply_to_message_id: int | None) -> dict[str, Any] | None:
        if reply_to_message_id is None:
            return None
        for item in self._load().values():
            if item.get("chat_id") != chat_id:
                continue
            if item.get("telegram_message_id") == reply_to_message_id:
                return item
            if reply_to_message_id in item.get("bot_message_ids", []):
                return item
        return None

    def start_feedback(self, chat_id: int, *, command: str, interaction: dict[str, Any] | None) -> None:
        data = self._load()
        data.setdefault("_feedback", {})[str(chat_id)] = {
            "state": "awaiting_correction",
            "command": command,
            "interaction_id": interaction.get("interaction_id") if interaction else None,
            "interaction": interaction,
            "timestamp": _now(),
        }
        self._save(data)

    def get_feedback(self, chat_id: int) -> dict[str, Any] | None:
        return self._load().get("_feedback", {}).get(str(chat_id))

    def update_feedback(self, chat_id: int, payload: dict[str, Any]) -> None:
        data = self._load()
        data.setdefault("_feedback", {})[str(chat_id)] = payload
        self._save(data)

    def pop_feedback(self, chat_id: int) -> dict[str, Any] | None:
        data = self._load()
        payload = data.get("_feedback", {}).pop(str(chat_id), None)
        self._save(data)
        return payload

    def has_issue_fingerprint(self, fingerprint: str) -> bool:
        return fingerprint in self._load().get("_issue_fingerprints", {})

    def remember_issue_fingerprint(self, fingerprint: str) -> None:
        data = self._load()
        data.setdefault("_issue_fingerprints", {})[fingerprint] = _now()
        self._save(data)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
