from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


FEEDBACK_TTL = timedelta(hours=24)
FINGERPRINT_TTL = timedelta(days=7)


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

    def latest_for_chat(self, chat_id: int, *, completed_only: bool = True) -> dict[str, Any] | None:
        items = []
        for item in self._load().values():
            if _is_service_record(item) or item.get("chat_id") != chat_id:
                continue
            if completed_only and item.get("status") not in {"completed", "completed_with_errors"}:
                continue
            items.append(item)
        return max(items, key=lambda item: item.get("timestamp", "")) if items else None

    def find_by_reply(self, chat_id: int, reply_to_message_id: int | None) -> dict[str, Any] | None:
        if reply_to_message_id is None:
            return None
        for item in self._load().values():
            if _is_service_record(item):
                continue
            if item.get("chat_id") != chat_id:
                continue
            if item.get("telegram_message_id") == reply_to_message_id:
                return item
            if reply_to_message_id in item.get("bot_message_ids", []):
                return item
        return None

    def start_feedback(
        self,
        chat_id: int,
        *,
        command: str,
        interaction: dict[str, Any] | None,
        state: str = "awaiting_correction",
    ) -> None:
        data = self._load()
        data.setdefault("_feedback", {})[str(chat_id)] = {
            "state": state,
            "command": command,
            "interaction_id": interaction.get("interaction_id") if interaction else None,
            "interaction": interaction,
            "timestamp": _now(),
        }
        self._save(data)

    def get_feedback(self, chat_id: int) -> dict[str, Any] | None:
        data = self._load()
        payload = data.get("_feedback", {}).get(str(chat_id))
        if not payload:
            return None
        if _expired(payload.get("timestamp"), FEEDBACK_TTL):
            data.get("_feedback", {}).pop(str(chat_id), None)
            self._save(data)
            return None
        return payload

    def update_feedback(self, chat_id: int, payload: dict[str, Any]) -> None:
        data = self._load()
        payload.setdefault("timestamp", _now())
        data.setdefault("_feedback", {})[str(chat_id)] = payload
        self._save(data)

    def pop_feedback(self, chat_id: int) -> dict[str, Any] | None:
        data = self._load()
        payload = data.get("_feedback", {}).pop(str(chat_id), None)
        self._save(data)
        return payload

    def remember_improvement(self, chat_id: int, improvement: dict[str, Any]) -> None:
        data = self._load()
        payload = dict(improvement)
        payload["timestamp"] = _now()
        values = data.setdefault("_improvements", {}).setdefault(str(chat_id), [])
        if isinstance(values, dict):
            values = [values]
            data["_improvements"][str(chat_id)] = values
        values.append(payload)
        self._save(data)

    def latest_improvement(self, chat_id: int) -> dict[str, Any] | None:
        values = self._improvements_for_chat(chat_id)
        return max(values, key=lambda item: item.get("timestamp", "")) if values else None

    def find_improvement_by_reply(self, chat_id: int, reply_to_message_id: int | None) -> dict[str, Any] | None:
        if reply_to_message_id is None:
            return None
        for item in self._improvements_for_chat(chat_id):
            if reply_to_message_id in item.get("bot_message_ids", []):
                return item
        return None

    def _improvements_for_chat(self, chat_id: int) -> list[dict[str, Any]]:
        raw = self._load().get("_improvements", {}).get(str(chat_id), [])
        values = [raw] if isinstance(raw, dict) else raw
        return [item for item in values if isinstance(item, dict) and not _expired(item.get("timestamp"), FEEDBACK_TTL)]

    def remember_backlog_list(self, chat_id: int, improvements: list[dict[str, Any]]) -> None:
        data = self._load()
        data.setdefault("_backlog_lists", {})[str(chat_id)] = {
            "chat_id": chat_id,
            "items": improvements,
            "timestamp": _now(),
        }
        self._save(data)

    def get_backlog_list(self, chat_id: int) -> dict[str, Any] | None:
        data = self._load()
        payload = data.get("_backlog_lists", {}).get(str(chat_id))
        if not payload:
            return None
        if _expired(payload.get("timestamp"), FEEDBACK_TTL):
            data.get("_backlog_lists", {}).pop(str(chat_id), None)
            self._save(data)
            return None
        return payload

    def remember_triage_list(self, chat_id: int, improvements: list[dict[str, Any]]) -> None:
        data = self._load()
        data.setdefault("_triage_lists", {})[str(chat_id)] = {
            "chat_id": chat_id,
            "items": improvements,
            "timestamp": _now(),
        }
        self._save(data)

    def get_triage_list(self, chat_id: int) -> dict[str, Any] | None:
        data = self._load()
        payload = data.get("_triage_lists", {}).get(str(chat_id))
        if not payload:
            return None
        if _expired(payload.get("timestamp"), FEEDBACK_TTL):
            data.get("_triage_lists", {}).pop(str(chat_id), None)
            self._save(data)
            return None
        return payload

    def remember_feedback_signal(self, improvement_id: str, signal: dict[str, Any]) -> bool:
        data = self._load()
        signals = data.setdefault("_feedback_signals", {}).setdefault(improvement_id, [])
        self._prune_feedback_signals(signals)
        normalized = _normalized_signal_text(signal.get("original"))
        if normalized and any(_normalized_signal_text(item.get("original")) == normalized for item in signals):
            self._save(data)
            return False
        payload = dict(signal)
        payload.setdefault("timestamp", _now())
        signals.append(payload)
        data["_feedback_signals"][improvement_id] = signals[-50:]
        self._save(data)
        return True

    def feedback_signals(self, improvement_id: str) -> list[dict[str, Any]]:
        data = self._load()
        signals = data.get("_feedback_signals", {}).get(improvement_id, [])
        self._prune_feedback_signals(signals)
        self._save(data)
        return signals if isinstance(signals, list) else []

    def has_issue_fingerprint(self, fingerprint: str) -> bool:
        data = self._load()
        self._prune_fingerprints(data)
        self._save(data)
        return fingerprint in data.get("_issue_fingerprints", {})

    def remember_issue_fingerprint(self, fingerprint: str) -> None:
        data = self._load()
        self._prune_fingerprints(data)
        data.setdefault("_issue_fingerprints", {})[fingerprint] = _now()
        self._save(data)

    def cleanup(self) -> None:
        data = self._load()
        self._prune_fingerprints(data)
        for chat_id, payload in list(data.get("_feedback", {}).items()):
            if _expired(payload.get("timestamp"), FEEDBACK_TTL):
                data.get("_feedback", {}).pop(chat_id, None)
        for chat_id, payload in list(data.get("_backlog_lists", {}).items()):
            if _expired(payload.get("timestamp"), FEEDBACK_TTL):
                data.get("_backlog_lists", {}).pop(chat_id, None)
        for chat_id, payload in list(data.get("_triage_lists", {}).items()):
            if _expired(payload.get("timestamp"), FEEDBACK_TTL):
                data.get("_triage_lists", {}).pop(chat_id, None)
        for signals in data.get("_feedback_signals", {}).values():
            if isinstance(signals, list):
                self._prune_feedback_signals(signals)
        self._save(data)

    def _prune_fingerprints(self, data: dict[str, Any]) -> None:
        fingerprints = data.get("_issue_fingerprints", {})
        for key, timestamp in list(fingerprints.items()):
            if _expired(timestamp, FINGERPRINT_TTL):
                fingerprints.pop(key, None)

    def _prune_feedback_signals(self, signals: list[dict[str, Any]]) -> None:
        for item in list(signals):
            if _expired(item.get("timestamp"), FINGERPRINT_TTL):
                signals.remove(item)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_service_record(value: Any) -> bool:
    if not isinstance(value, dict):
        return True
    interaction_id = value.get("interaction_id")
    return not interaction_id or str(interaction_id).startswith("_")


def _expired(timestamp: Any, ttl: timedelta) -> bool:
    try:
        parsed = datetime.fromisoformat(str(timestamp))
    except (TypeError, ValueError):
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - parsed > ttl


def _normalized_signal_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())
