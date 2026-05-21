from __future__ import annotations

from typing import Any

from .http import request_json
from .models import StudyItem, TaskItem, normalize_effort


NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(self, token: str, tasks_db: str, study_db: str, projects_db: str):
        self.token = token
        self.tasks_db = tasks_db
        self.study_db = study_db
        self.projects_db = projects_db

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def list_projects(self) -> list[dict[str, str]]:
        if not self.token or not self.projects_db:
            return []
        payload = {"page_size": 100}
        data = request_json(
            "POST",
            f"https://api.notion.com/v1/databases/{self.projects_db}/query",
            headers=self.headers,
            payload=payload,
        )
        projects = []
        for row in data.get("results", []):
            props = row.get("properties", {})
            projects.append(
                {
                    "id": row.get("id", ""),
                    "name": _title(props.get("Проект")),
                    "area": _select(props.get("Направление")),
                    "status": _select(props.get("Статус")),
                    "url": row.get("url", ""),
                }
            )
        return [p for p in projects if p["name"]]

    def create_task(self, item: TaskItem, *, source: str = "Telegram") -> str:
        payload = {
            "parent": {"database_id": self.tasks_db},
            "properties": _task_properties(item),
            "children": _task_children(item, source),
        }
        data = request_json("POST", "https://api.notion.com/v1/pages", headers=self.headers, payload=payload)
        return data.get("url", "")

    def create_study(self, item: StudyItem) -> str:
        payload = {"parent": {"database_id": self.study_db}, "properties": _study_properties(item)}
        data = request_json("POST", "https://api.notion.com/v1/pages", headers=self.headers, payload=payload)
        return data.get("url", "")

    def update_task(self, page_id: str, item: TaskItem) -> None:
        request_json(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=self.headers,
            payload={"properties": _task_properties(item)},
        )

    def update_study(self, page_id: str, item: StudyItem) -> None:
        request_json(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=self.headers,
            payload={"properties": _study_properties(item)},
        )


def _task_children(item: TaskItem, source: str) -> list[dict[str, Any]]:
    lines = [
        ("Описание", item.description),
        ("Желаемый результат", item.desired_result),
        ("Источник", source),
    ]
    children = []
    for title, text in lines:
        if not text:
            continue
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"{title}: {text}"}}]},
            }
        )
    return children


def _task_properties(item: TaskItem) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "Task": _title_prop(item.title),
        "Status": _status_prop("Inbox"),
        "Kind": _select_prop("Task"),
        "Priority": _select_prop(_priority(item.priority)),
        "Sync status": _select_prop("Not synced"),
        "Sync → Todoist": {"checkbox": False},
        "Project": _rich_text_prop(item.project or ""),
        "Area": _select_prop(_area_for_tasks(item.area)),
        "Next Step": _rich_text_prop(item.next_step),
    }
    effort = normalize_effort(item.effort_minutes)
    if effort:
        properties["Effort"] = _select_prop(effort)
    else:
        properties["Effort"] = _select_prop(None)
    properties["Due"] = _date_prop(item.due_date) if item.due_date else {"date": None}
    return properties


def _study_properties(item: StudyItem) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "Вопрос / проблема": _title_prop(item.question),
        "Расширенное описание": _rich_text_prop(item.description),
        "Отрасль": _rich_text_prop(item.industry),
        "Тип исследования": _select_prop(_research_type(item.research_type)),
        "Проект": _rich_text_prop(item.project or ""),
        "Направление": _select_prop(_area(item.area)),
        "Приоритет": _select_prop(_priority(item.priority)),
        "Формат результата": _select_prop(_result_format(item.result_format)),
        "Источник задачи": _rich_text_prop(item.source or "Telegram"),
        "Статус": _select_prop("Inbox"),
        "Срок": _date_prop(item.due_date) if item.due_date else {"date": None},
    }
    return properties


def _title(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    return "".join(part.get("plain_text", "") for part in prop.get("title", []))


def _select(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    value = prop.get("select") or prop.get("status")
    return value.get("name", "") if value else ""


def _title_prop(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def _rich_text_prop(value: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]} if value else {"rich_text": []}


def _select_prop(value: str | None) -> dict[str, Any]:
    return {"select": {"name": value}} if value else {"select": None}


def _status_prop(value: str) -> dict[str, Any]:
    return {"status": {"name": value}}


def _date_prop(value: str) -> dict[str, Any]:
    return {"date": {"start": value}}


def _priority(value: str | None) -> str:
    return value if value in {"P1", "P2", "P3"} else "P2"


def _area(value: str | None) -> str:
    return value if value in {"Работа", "Бизнес", "Личное развитие", "Семья", "Прочее"} else "Прочее"


def _area_for_tasks(value: str | None) -> str:
    return value if value in {"Работа", "Бизнес", "Личное развитие", "Семья"} else "Операционка"


def _research_type(value: str | None) -> str:
    return value if value in {"Простое", "Глубокое"} else "Простое"


def _result_format(value: str | None) -> str:
    allowed = {"Краткая справка", "Подробная справка", "Memo", "Таблица", "Telegram-дайджест"}
    return value if value in allowed else "Краткая справка"
