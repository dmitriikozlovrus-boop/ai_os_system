from __future__ import annotations

from typing import Any

from .http import request_json
from .models import TaskItem


class TodoistClient:
    def __init__(self, api_token: str, enabled: bool):
        self.api_token = api_token
        self.enabled = enabled

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

    def create_task(self, item: TaskItem) -> str | None:
        if not self.enabled:
            return None
        payload: dict[str, Any] = {
            "content": item.title,
            "description": item.description,
            "priority": _priority(item.priority),
        }
        if item.due_date:
            payload["due_date"] = item.due_date
        response = request_json(
            "POST",
            "https://api.todoist.com/rest/v2/tasks",
            headers=self.headers,
            payload=payload,
        )
        return response.get("id")


def _priority(value: str) -> int:
    return {"P1": 4, "P2": 3, "P3": 2}.get(value, 1)
