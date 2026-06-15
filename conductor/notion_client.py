from __future__ import annotations

from typing import Any

from .http import request_json
from .models import StudyItem, TaskItem


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
                    "name": _title(props.get("Project")),
                    "area": "",
                    "status": _select(props.get("Статус проекта")),
                    "url": row.get("url", ""),
                }
            )
        return [p for p in projects if p["name"]]

    def create_task(
        self,
        item: TaskItem,
        *,
        source: str = "Telegram",
        projects: list[dict[str, str]] | None = None,
    ) -> str:
        project_id = self._find_project_id(item.project, projects=projects)
        payload = {
            "parent": {"database_id": self.tasks_db},
            "properties": _task_properties(item, project_id=project_id),
            "children": _task_children(item, source),
        }
        data = request_json("POST", "https://api.notion.com/v1/pages", headers=self.headers, payload=payload)
        return data.get("url", "")

    def create_study(self, item: StudyItem) -> str:
        payload = {"parent": {"database_id": self.study_db}, "properties": _study_properties(item)}
        data = request_json("POST", "https://api.notion.com/v1/pages", headers=self.headers, payload=payload)
        return data.get("url", "")

    def update_task(
        self,
        page_id: str,
        item: TaskItem,
        *,
        projects: list[dict[str, str]] | None = None,
    ) -> None:
        project_id = self._find_project_id(item.project, projects=projects)
        request_json(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=self.headers,
            payload={"properties": _task_properties(item, project_id=project_id)},
        )

    def update_study(self, page_id: str, item: StudyItem) -> None:
        request_json(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=self.headers,
            payload={"properties": _study_properties(item)},
        )

    def _find_project_id(
        self,
        name: str | None,
        *,
        projects: list[dict[str, str]] | None = None,
    ) -> str | None:
        if not name:
            return None
        normalized = " ".join(name.casefold().split())
        for project in projects if projects is not None else self.list_projects():
            if " ".join(project["name"].casefold().split()) == normalized:
                return project["id"]
        return None


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


def _task_properties(item: TaskItem, *, project_id: str | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "Task": _title_prop(item.title),
        "Статус": _status_prop("Backlog"),
        "Source": _select_prop("Telegram Assistant"),
        "Sync status": _select_prop("Not synced"),
        "Strategic Impact": _select_prop(_strategic_impact(item.priority)),
        "Time zone": _select_prop("America/Mexico_City"),
    }
    properties["Оценка времени"] = _select_prop(_effort(item.effort_minutes))
    properties["Deadline"] = _date_prop(item.due_date) if item.due_date else {"date": None}
    if project_id:
        properties["Проект"] = {"relation": [{"id": project_id}]}
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


def _strategic_impact(value: str | None) -> str:
    return {"P1": "10", "P2": "8", "P3": "5"}.get(value or "", "2")


def _effort(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    choices = [5, 10, 15, 20, 25, 30, 45, 60, 75, 90, 105, 120]
    selected = min(choices, key=lambda value: abs(value - minutes))
    if selected < 60:
        return f"{selected} минут"
    if selected == 60:
        return "1 час"
    hours, remainder = divmod(selected, 60)
    return f"{hours} час{'а' if hours in {2, 3, 4} else 'ов'} {remainder} минут" if remainder else f"{hours} часа"


def _area(value: str | None) -> str:
    return value if value in {"Работа", "Бизнес", "Личное развитие", "Семья", "Прочее"} else "Прочее"


def _research_type(value: str | None) -> str:
    return value if value in {"Простое", "Глубокое"} else "Простое"


def _result_format(value: str | None) -> str:
    allowed = {"Краткая справка", "Подробная справка", "Memo", "Таблица", "Telegram-дайджест"}
    return value if value in allowed else "Краткая справка"
