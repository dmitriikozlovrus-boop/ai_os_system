from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from .http import request_json
from .models import (
    IMPROVEMENT_CHANGE_LOCATIONS,
    IMPROVEMENT_OPEN_STATUSES,
    IMPROVEMENT_PRIORITIES,
    IMPROVEMENT_TYPES,
    GoodsItem,
    ImprovementRecord,
    ImprovementSummary,
    StudyItem,
    SystemIssueRecord,
    SystemIssueSummary,
    TaskItem,
)


NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(
        self,
        token: str,
        tasks_db: str,
        study_db: str,
        projects_db: str,
        goods_db: str = "",
        system_issues_db: str = "",
        improvements_db: str = "",
    ):
        self.token = token
        self.tasks_db = tasks_db
        self.study_db = study_db
        self.projects_db = projects_db
        self.goods_db = goods_db
        self.system_issues_db = system_issues_db
        self.improvements_db = improvements_db

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

    def create_goods(self, item: GoodsItem, *, projects: list[dict[str, str]] | None = None) -> str:
        if not self.goods_db:
            raise RuntimeError("NOTION_GOODS_DATABASE_ID is not configured")
        if not item.title.strip():
            raise RuntimeError("Goods title is required")
        project_id = self._find_project_id(item.project, projects=projects)
        payload = {
            "parent": {"database_id": self.goods_db},
            "properties": _goods_properties(item, project_id=project_id),
        }
        data = request_json("POST", "https://api.notion.com/v1/pages", headers=self.headers, payload=payload)
        return data.get("url", "")

    def create_system_issue(self, issue: SystemIssueRecord) -> str:
        if not self.system_issues_db:
            raise RuntimeError("NOTION_SYSTEM_ISSUES_DATABASE_ID is not configured")
        payload = {
            "parent": {"database_id": self.system_issues_db},
            "properties": _system_issue_properties(issue),
        }
        data = request_json("POST", "https://api.notion.com/v1/pages", headers=self.headers, payload=payload)
        return data.get("url", "")

    def update_system_issue(self, page_id: str, *, solution: str, status: str | None = None) -> None:
        properties: dict[str, Any] = {"Решение": _rich_text_prop(solution)}
        if status:
            properties["Статус"] = _select_prop(status)
        request_json(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=self.headers,
            payload={"properties": properties},
        )

    def list_recent_system_issues(
        self,
        *,
        issue_type: str | None = None,
        database: str | None = None,
        days: int = 90,
        limit: int = 30,
    ) -> list[SystemIssueSummary]:
        if not self.token or not self.system_issues_db:
            return []
        filters: list[dict[str, Any]] = [
            {
                "property": "Дата обнаружения",
                "date": {"on_or_after": (date.today() - timedelta(days=days)).isoformat()},
            }
        ]
        if issue_type:
            filters.append({"property": "Тип ошибки", "select": {"equals": issue_type}})
        if database:
            filters.append({"property": "База данных", "select": {"equals": database}})
        payload: dict[str, Any] = {
            "page_size": max(1, min(limit, 100)),
            "sorts": [{"property": "Дата обнаружения", "direction": "descending"}],
            "filter": {"and": filters},
        }
        data = request_json(
            "POST",
            f"https://api.notion.com/v1/databases/{self.system_issues_db}/query",
            headers=self.headers,
            payload=payload,
        )
        return [_system_issue_summary(row) for row in data.get("results", [])]

    def find_open_improvements_for_issues(
        self,
        *,
        related_issue_urls: list[str],
        title: str = "",
        improvement_type: str = "",
        change_location: str = "",
        limit: int = 10,
    ) -> list[ImprovementSummary]:
        if not self.token or not self.improvements_db:
            return []
        issue_ids = []
        for url in related_issue_urls:
            try:
                issue_ids.append(notion_page_id_from_reference(url))
            except ValueError:
                continue
        filters: list[dict[str, Any]] = [
            {"or": [{"property": "Статус", "select": {"equals": status}} for status in sorted(IMPROVEMENT_OPEN_STATUSES)]}
        ]
        if issue_ids:
            filters.append({"or": [{"property": "Какие ошибки исправляет", "relation": {"contains": page_id}} for page_id in issue_ids]})
        elif title:
            filters.append({"property": "Улучшение", "title": {"equals": title[:2000]}})
        payload: dict[str, Any] = {"page_size": max(1, min(limit, 100)), "filter": {"and": filters}}
        data = request_json(
            "POST",
            f"https://api.notion.com/v1/databases/{self.improvements_db}/query",
            headers=self.headers,
            payload=payload,
        )
        summaries = [_improvement_summary(row) for row in data.get("results", [])]
        normalized_title = _normalize_text(title)
        if normalized_title:
            summaries = [
                item
                for item in summaries
                if item.related_issue_urls
                or (
                    _normalize_text(item.title) == normalized_title
                    and item.improvement_type == improvement_type
                    and item.change_location == change_location
                )
            ]
        return summaries

    def create_improvement(self, improvement: ImprovementRecord, *, related_issue_urls: list[str]) -> str:
        if not self.improvements_db:
            raise RuntimeError("NOTION_IMPROVEMENTS_DATABASE_ID is not configured")
        payload = {
            "parent": {"database_id": self.improvements_db},
            "properties": _improvement_properties(
                improvement,
                related_issue_urls=related_issue_urls,
                forbidden_relation_ids=[self.improvements_db, self.system_issues_db],
            ),
        }
        data = request_json("POST", "https://api.notion.com/v1/pages", headers=self.headers, payload=payload)
        return data.get("url", "")

    def add_issues_to_improvement(self, improvement_page_id: str, *, related_issue_urls: list[str]) -> None:
        improvement_page_id = notion_page_id_from_reference(improvement_page_id)
        issue_ids = _relation_page_ids(related_issue_urls, forbidden_ids=[self.improvements_db, self.system_issues_db])
        relation = [{"id": page_id} for page_id in issue_ids]
        request_json(
            "PATCH",
            f"https://api.notion.com/v1/pages/{improvement_page_id}",
            headers=self.headers,
            payload={"properties": {"Какие ошибки исправляет": {"relation": relation}}},
        )

    def get_improvement(self, improvement_ref: str) -> ImprovementSummary:
        page_id = notion_page_id_from_reference(improvement_ref)
        data = request_json("GET", f"https://api.notion.com/v1/pages/{page_id}", headers=self.headers)
        return _improvement_summary(data)

    def get_system_issues_by_references(self, issue_refs: list[str], *, limit: int = 10) -> list[SystemIssueSummary]:
        issues = []
        for reference in issue_refs[:limit]:
            page_id = notion_page_id_from_reference(reference)
            data = request_json("GET", f"https://api.notion.com/v1/pages/{page_id}", headers=self.headers)
            issues.append(_system_issue_summary(data))
        return issues

    def save_improvement_technical_spec(self, improvement_ref: str, markdown: str, *, today: str) -> None:
        page_id = notion_page_id_from_reference(improvement_ref)
        self._archive_existing_technical_spec(page_id)
        payload = {
            "children": _technical_spec_blocks(markdown, today=today),
        }
        request_json(
            "PATCH",
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=self.headers,
            payload=payload,
        )

    def _archive_existing_technical_spec(self, page_id: str) -> None:
        data = request_json(
            "GET",
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100",
            headers=self.headers,
        )
        blocks = data.get("results", []) or []
        deleting = False
        for block in blocks:
            block_id = block.get("id")
            if _block_plain_text(block).strip() == "Техническое задание для Codex":
                deleting = True
            if deleting and block_id:
                request_json(
                    "PATCH",
                    f"https://api.notion.com/v1/blocks/{block_id}",
                    headers=self.headers,
                    payload={"archived": True},
                )
            if deleting and "CONDUCTOR_TECH_SPEC_END" in _block_plain_text(block):
                break

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


def _goods_properties(item: GoodsItem, *, project_id: str | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "Наименование предмета": _title_prop(item.title.strip()),
        "Статус": _status_prop(item.status or "Не куплено"),
        "Источник": _select_prop(item.source or "ИИ"),
    }
    optional_props = {
        "Тип товара": _select_prop(item.goods_type) if item.goods_type else None,
        "Приоритет": _select_prop(item.priority) if item.priority else None,
        "Цена": _number_prop(item.price) if item.price is not None else None,
        "Валюта": _select_prop(item.currency) if item.currency else None,
        "Пользователь товара": _select_prop(item.goods_user) if item.goods_user else None,
        "Место использования": _select_prop(item.usage_place) if item.usage_place else None,
        "Стрим": _select_prop(item.stream) if item.stream else None,
        "Ссылка": _url_prop(item.url) if item.url else None,
    }
    for name, prop in optional_props.items():
        if prop is not None:
            properties[name] = prop
    if project_id:
        properties["Проект"] = {"relation": [{"id": project_id}]}
    return properties


def _system_issue_properties(issue: SystemIssueRecord) -> dict[str, Any]:
    classification = issue.classification
    return {
        "Краткое описание ошибки": _title_prop(_issue_title(classification)),
        "Тип ошибки": _select_prop(classification.issue_type),
        "Статус": _select_prop(issue.status),
        "Критичность": _select_prop(classification.severity),
        "Способ обнаружения": _select_prop(issue.detection_method),
        "База данных": _select_prop(classification.database),
        "Входные данные": _rich_text_prop(issue.input_data),
        "Описание": _rich_text_prop(issue.description),
        "Причина ошибки": _rich_text_prop(classification.probable_cause or "Требуется анализ"),
        "Решение": _rich_text_prop(issue.solution),
        "Дата обнаружения": _date_prop(issue.detected_date),
    }


def _improvement_properties(
    improvement: ImprovementRecord,
    *,
    related_issue_urls: list[str],
    forbidden_relation_ids: list[str] | None = None,
) -> dict[str, Any]:
    issue_ids = _relation_page_ids(related_issue_urls, forbidden_ids=forbidden_relation_ids or [])
    if improvement.improvement_type not in IMPROVEMENT_TYPES:
        raise ValueError(f"Unknown Improvement type: {improvement.improvement_type}")
    if improvement.change_location not in IMPROVEMENT_CHANGE_LOCATIONS:
        raise ValueError(f"Unknown Improvement change location: {improvement.change_location}")
    if improvement.priority not in IMPROVEMENT_PRIORITIES:
        raise ValueError(f"Unknown Improvement priority: {improvement.priority}")
    return {
        "Улучшение": _title_prop(improvement.title),
        "Описание": _rich_text_prop(improvement.description),
        "Что изменить": _rich_text_prop(improvement.suggested_change),
        "Тип улучшения": _select_prop(improvement.improvement_type),
        "Где изменить": _select_prop(improvement.change_location),
        "Приоритет": _select_prop(improvement.priority),
        "Статус": _select_prop("Идея"),
        "Какие ошибки исправляет": {"relation": [{"id": page_id} for page_id in issue_ids]},
    }


def _system_issue_summary(row: dict[str, Any]) -> SystemIssueSummary:
    props = row.get("properties", {})
    return SystemIssueSummary(
        page_id=row.get("id", ""),
        url=row.get("url", ""),
        title=_title(props.get("Краткое описание ошибки")),
        issue_type=_select(props.get("Тип ошибки")),
        severity=_select(props.get("Критичность")),
        database=_select(props.get("База данных")),
        input_data=_rich_text(props.get("Входные данные")),
        description=_rich_text(props.get("Описание")),
        solution=_rich_text(props.get("Решение")),
        detected_date=_date_value(props.get("Дата обнаружения")),
    )


def _improvement_summary(row: dict[str, Any]) -> ImprovementSummary:
    props = row.get("properties", {})
    relation = props.get("Какие ошибки исправляет", {}).get("relation", []) or []
    return ImprovementSummary(
        page_id=row.get("id", ""),
        url=row.get("url", ""),
        title=_title(props.get("Улучшение")),
        status=_select(props.get("Статус")),
        improvement_type=_select(props.get("Тип улучшения")),
        change_location=_select(props.get("Где изменить")),
        related_issue_urls=[item.get("id", "") for item in relation if item.get("id")],
    )


def _technical_spec_blocks(markdown: str, *, today: str) -> list[dict[str, Any]]:
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Техническое задание для Codex"}}]},
        },
        _paragraph_block("Статус проекта ТЗ: Черновик"),
        _paragraph_block(f"Дата формирования: {today}"),
    ]
    for chunk in _chunks(markdown, 1800):
        blocks.append(_paragraph_block(chunk))
    blocks.append(_paragraph_block("<!-- CONDUCTOR_TECH_SPEC_END -->"))
    return blocks


def _paragraph_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
    }


def _chunks(text: str, size: int) -> list[str]:
    if not text:
        return []
    return [text[index : index + size] for index in range(0, len(text), size)]


def _block_plain_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    if not block_type:
        return ""
    rich_text = (block.get(block_type) or {}).get("rich_text", [])
    return "".join(part.get("plain_text", "") for part in rich_text)


def _issue_title(classification: Any) -> str:
    title = classification.title or classification.expected_result or classification.actual_result or "Ошибка Дирижера"
    return f"{classification.issue_type}: {title}"[:2000]


def _title(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    return "".join(part.get("plain_text", "") for part in prop.get("title", []))


def _select(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    value = prop.get("select") or prop.get("status")
    return value.get("name", "") if value else ""


def _rich_text(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    return "".join(part.get("plain_text", "") for part in prop.get("rich_text", []))


def _date_value(prop: dict[str, Any] | None) -> str:
    if not prop or not prop.get("date"):
        return ""
    return str(prop["date"].get("start") or "")


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


def _number_prop(value: float) -> dict[str, Any]:
    return {"number": value}


def _url_prop(value: str) -> dict[str, Any]:
    return {"url": value}


def notion_page_id_from_reference(value: str) -> str:
    reference = str(value or "").strip()
    if not reference:
        raise ValueError("Notion page reference is empty")
    uuid_match = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        reference,
    )
    if uuid_match:
        return uuid_match.group(1).lower()
    compact_matches = re.findall(r"(?<![0-9a-fA-F])([0-9a-fA-F]{32})(?![0-9a-fA-F])", reference)
    if compact_matches:
        raw = compact_matches[-1].lower()
        return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
    raise ValueError(f"Invalid Notion page reference: {reference[:120]}")


def _relation_page_ids(references: list[str], *, forbidden_ids: list[str]) -> list[str]:
    forbidden = set()
    for value in forbidden_ids:
        if not value:
            continue
        try:
            forbidden.add(notion_page_id_from_reference(value))
        except ValueError:
            continue
    result = []
    seen = set()
    for reference in references:
        page_id = notion_page_id_from_reference(reference)
        if page_id in forbidden:
            raise ValueError("Notion database ID cannot be used as a page relation ID")
        if page_id in seen:
            continue
        seen.add(page_id)
        result.append(page_id)
    return result


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


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
