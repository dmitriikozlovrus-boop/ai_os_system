from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .http import request_json
from .models import TaskItem

API_BASE = "https://api.todoist.com/api/v1"


class TodoistClient:
    def __init__(self, api_token: str, enabled: bool):
        self.api_token = api_token
        self.enabled = enabled

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

    def list_tasks(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        tasks: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            response = request_json(
                "GET",
                f"{API_BASE}/tasks",
                headers=self.headers,
                query={"cursor": cursor, "limit": 200},
            )
            if isinstance(response, list):
                tasks.extend(response)
                break
            tasks.extend(response.get("results", []))
            cursor = response.get("next_cursor")
            if not cursor:
                break
        return tasks

    def list_labels(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        labels: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            response = request_json(
                "GET",
                f"{API_BASE}/labels",
                headers=self.headers,
                query={"cursor": cursor, "limit": 200},
            )
            if isinstance(response, list):
                labels.extend(response)
                break
            labels.extend(response.get("results", []))
            cursor = response.get("next_cursor")
            if not cursor:
                break
        return labels

    def create_label(self, name: str) -> str | None:
        if not self.enabled:
            return None
        response = request_json(
            "POST",
            f"{API_BASE}/labels",
            headers=self.headers,
            payload={"name": name},
        )
        return response.get("id")

    def list_completed_tasks(self, since: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        start = _as_datetime(since)
        now = datetime.now(timezone.utc)
        tasks: list[dict[str, Any]] = []
        while start < now:
            end = min(start + timedelta(days=89), now + timedelta(seconds=1))
            cursor: str | None = None
            while True:
                response = request_json(
                    "GET",
                    f"{API_BASE}/tasks/completed/by_completion_date",
                    headers=self.headers,
                    query={
                        "since": start.isoformat().replace("+00:00", "Z"),
                        "until": end.isoformat().replace("+00:00", "Z"),
                        "cursor": cursor,
                        "limit": 200,
                    },
                )
                page = response.get("items", [])
                for task in page:
                    task["is_completed"] = True
                    task["updated_at"] = task.get("completed_at") or task.get("added_at")
                tasks.extend(page)
                cursor = response.get("next_cursor")
                if not cursor:
                    break
            start = end
        return tasks

    def get_task(self, task_id: str) -> dict[str, Any]:
        return request_json("GET", f"{API_BASE}/tasks/{task_id}", headers=self.headers)

    def create_task(self, item: TaskItem | dict[str, Any]) -> str | None:
        if not self.enabled:
            return None
        payload = _task_payload(item)
        response = request_json(
            "POST",
            f"{API_BASE}/tasks",
            headers=self.headers,
            payload=payload,
        )
        return response.get("id")

    def update_task(self, task_id: str, item: dict[str, Any]) -> None:
        request_json(
            "POST",
            f"{API_BASE}/tasks/{task_id}",
            headers=self.headers,
            payload=_task_payload(item),
        )

    def update_task_labels(self, task_id: str, labels: list[str]) -> None:
        request_json(
            "POST",
            f"{API_BASE}/tasks/{task_id}",
            headers=self.headers,
            payload={"labels": labels},
        )

    def close_task(self, task_id: str) -> None:
        request_json("POST", f"{API_BASE}/tasks/{task_id}/close", headers=self.headers)

    def reopen_task(self, task_id: str) -> None:
        request_json("POST", f"{API_BASE}/tasks/{task_id}/reopen", headers=self.headers)

    def delete_task(self, task_id: str) -> None:
        request_json("DELETE", f"{API_BASE}/tasks/{task_id}", headers=self.headers)


def _task_payload(item: TaskItem | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, TaskItem):
        title = item.title
        description = item.description
        priority = item.priority
        due_date = item.due_date
        deadline = None
    else:
        title = str(item.get("title") or "")
        description = str(item.get("description") or "")
        priority = str(item.get("priority") or "")
        due_date = item.get("due_date")
        deadline = item.get("deadline")
    payload: dict[str, Any] = {
        "content": title,
        "description": description,
        "priority": _priority(priority),
    }
    if due_date:
        payload["due_date"] = due_date
    if deadline:
        payload["deadline_date"] = deadline
    labels = item.get("labels") if isinstance(item, dict) else None
    if isinstance(item, dict) and "project_name" in item:
        labels = [item["project_name"]] if item.get("project_name") else []
    if labels is not None:
        payload["labels"] = labels
    return payload


def _priority(value: str) -> int:
    return {"P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(value, 4)


def todoist_priority(value: int | str | None) -> str:
    try:
        number = int(value or 1)
    except (TypeError, ValueError):
        number = 1
    return {1: "P1", 2: "P2", 3: "P3"}.get(number, "P4")


def _as_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime(2007, 1, 1, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
