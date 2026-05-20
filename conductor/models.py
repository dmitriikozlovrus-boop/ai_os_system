from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


AREAS = {"Работа", "Бизнес", "Личное развитие", "Семья", "Прочее"}
TASK_PRIORITIES = {"P1", "P2", "P3"}
PROJECT_PRIORITIES = {"P1", "P2", "P3", "P4"}
RESEARCH_TYPES = {"Простое", "Глубокое"}
RESULT_FORMATS = {"Краткая справка", "Подробная справка", "Memo", "Таблица", "Telegram-дайджест"}


@dataclass
class TaskItem:
    title: str
    description: str
    desired_result: str
    project: str | None
    area: str | None
    due_date: str | None
    effort_minutes: int | None
    priority: str
    next_step: str
    confidence: float
    missing: list[str] = field(default_factory=list)


@dataclass
class StudyItem:
    question: str
    description: str
    industry: str
    research_type: str
    project: str | None
    area: str | None
    priority: str
    result_format: str
    due_date: str | None
    source: str
    confidence: float
    missing: list[str] = field(default_factory=list)


@dataclass
class Classification:
    tasks: list[TaskItem]
    studies: list[StudyItem]
    notes: list[str]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_effort(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    if minutes <= 5:
        return "5m"
    if minutes <= 15:
        return "15m"
    if minutes <= 30:
        return "30m"
    if minutes <= 60:
        return "1h"
    return "2h+"


def classification_from_dict(data: dict[str, Any]) -> Classification:
    tasks = []
    for item in data.get("tasks", []) or []:
        tasks.append(
            TaskItem(
                title=str(item.get("title") or "").strip(),
                description=str(item.get("description") or "").strip(),
                desired_result=str(item.get("desired_result") or "").strip(),
                project=(str(item.get("project")).strip() if item.get("project") else None),
                area=(str(item.get("area")).strip() if item.get("area") else None),
                due_date=(str(item.get("due_date")).strip() if item.get("due_date") else None),
                effort_minutes=_as_int(item.get("effort_minutes")),
                priority=str(item.get("priority") or "P2").strip(),
                next_step=str(item.get("next_step") or "").strip(),
                confidence=_as_float(item.get("confidence"), 0.0),
                missing=[str(x) for x in item.get("missing", [])],
            )
        )

    studies = []
    for item in data.get("studies", []) or []:
        studies.append(
            StudyItem(
                question=str(item.get("question") or "").strip(),
                description=str(item.get("description") or "").strip(),
                industry=str(item.get("industry") or "Не определено").strip(),
                research_type=str(item.get("research_type") or "Простое").strip(),
                project=(str(item.get("project")).strip() if item.get("project") else None),
                area=(str(item.get("area")).strip() if item.get("area") else None),
                priority=str(item.get("priority") or "P2").strip(),
                result_format=str(item.get("result_format") or "Краткая справка").strip(),
                due_date=(str(item.get("due_date")).strip() if item.get("due_date") else None),
                source=str(item.get("source") or "").strip(),
                confidence=_as_float(item.get("confidence"), 0.0),
                missing=[str(x) for x in item.get("missing", [])],
            )
        )

    return Classification(tasks=tasks, studies=studies, notes=[str(x) for x in data.get("notes", [])])
