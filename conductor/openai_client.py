from __future__ import annotations

import json
from typing import Any

from .http import request_json, request_multipart
from .models import Classification, classification_from_dict


CLASSIFIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "desired_result": {"type": "string"},
                    "project": {"type": ["string", "null"]},
                    "area": {"type": ["string", "null"], "enum": ["Работа", "Бизнес", "Личное развитие", "Семья", "Прочее", None]},
                    "due_date": {"type": ["string", "null"], "description": "ISO date YYYY-MM-DD if present"},
                    "effort_minutes": {"type": ["integer", "null"], "minimum": 5},
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "next_step": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "missing": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "description",
                    "desired_result",
                    "project",
                    "area",
                    "due_date",
                    "effort_minutes",
                    "priority",
                    "next_step",
                    "confidence",
                    "missing",
                ],
            },
        },
        "studies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "question": {"type": "string"},
                    "description": {"type": "string"},
                    "industry": {"type": "string"},
                    "research_type": {"type": "string", "enum": ["Простое", "Глубокое"]},
                    "project": {"type": ["string", "null"]},
                    "area": {"type": ["string", "null"], "enum": ["Работа", "Бизнес", "Личное развитие", "Семья", "Прочее", None]},
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "result_format": {
                        "type": "string",
                        "enum": ["Краткая справка", "Подробная справка", "Memo", "Таблица", "Telegram-дайджест"],
                    },
                    "due_date": {"type": ["string", "null"], "description": "ISO date YYYY-MM-DD if present"},
                    "source": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "missing": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "question",
                    "description",
                    "industry",
                    "research_type",
                    "project",
                    "area",
                    "priority",
                    "result_format",
                    "due_date",
                    "source",
                    "confidence",
                    "missing",
                ],
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tasks", "studies", "notes"],
}


class OpenAIClient:
    def __init__(self, api_key: str, model: str, transcribe_model: str):
        self.api_key = api_key
        self.model = model
        self.transcribe_model = transcribe_model

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def classify(self, text: str, *, projects: list[dict[str, str]], today: str) -> Classification:
        if not self.api_key:
            return self._fallback(text)

        project_lines = "\n".join(
            f"- {p.get('name')} | направление: {p.get('area') or 'не указано'} | статус: {p.get('status') or 'не указано'}"
            for p in projects
        )
        system = (
            "Ты классификатор сервиса 'Дирижер'. Работай строго по ТЗ:\n"
            "- Задача = любое действие кроме простого чтения/изучения.\n"
            "- Вопрос на изучение = чтение, просмотр, анализ информации или справка.\n"
            "- Не мельчи: объединяй близкие действия в одну сущность, если это один смысловой результат.\n"
            "- Если проект неясен, поставь project=null и добавь 'project' в missing.\n"
            "- Если срок не указан, поставь due_date=null и добавь 'due_date' в missing.\n"
            "- Если уверенность по проекту/типу/сроку ниже 0.70, добавь соответствующее поле в missing.\n"
            "- Расширяй описание так, чтобы через месяц было понятно, что сделать и зачем.\n"
            "- Даты возвращай ISO YYYY-MM-DD. Сегодня: " + today + ".\n"
            "Направления: Работа, Бизнес, Личное развитие, Семья, Прочее.\n"
            "Существующие проекты:\n" + (project_lines or "- пока нет проектов") + "\n"
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conductor_classification",
                    "schema": CLASSIFIER_SCHEMA,
                    "strict": True,
                }
            },
        }
        data = request_json(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={**self.headers, "Content-Type": "application/json"},
            payload=payload,
            timeout=90,
        )
        raw = _extract_response_text(data)
        return classification_from_dict(json.loads(raw))

    def transcribe(self, filename: str, data: bytes, content_type: str = "audio/ogg") -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for voice transcription")
        response = request_multipart(
            "https://api.openai.com/v1/audio/transcriptions",
            headers=self.headers,
            fields={"model": self.transcribe_model, "response_format": "json", "language": "ru"},
            files={"file": (filename, data, content_type)},
            timeout=120,
        )
        return str(response.get("text") or "").strip()

    def _fallback(self, text: str) -> Classification:
        task_words = ("позвон", "напиш", "найти", "посчит", "подготов", "договор", "сдел", "отправ")
        study_words = ("изуч", "разобраться в", "понять", "исслед", "собрать справ")
        lower = text.lower()
        data: dict[str, Any] = {"tasks": [], "studies": [], "notes": ["fallback classifier"]}
        if any(word in lower for word in task_words):
            data["tasks"].append(
                {
                    "title": text[:80],
                    "description": text,
                    "desired_result": "Понятный выполненный результат по исходному сообщению.",
                    "project": None,
                    "area": None,
                    "due_date": None,
                    "effort_minutes": 30,
                    "priority": "P2",
                    "next_step": "Уточнить проект и срок.",
                    "confidence": 0.45,
                    "missing": ["project", "due_date"],
                }
            )
        if any(word in lower for word in study_words):
            data["studies"].append(
                {
                    "question": text[:80],
                    "description": text,
                    "industry": "Не определено",
                    "research_type": "Простое",
                    "project": None,
                    "area": None,
                    "priority": "P2",
                    "result_format": "Краткая справка",
                    "due_date": None,
                    "source": "Telegram",
                    "confidence": 0.45,
                    "missing": ["project", "due_date"],
                }
            )
        return classification_from_dict(data)


def _extract_response_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and "text" in content:
                parts.append(content["text"])
    if parts:
        return "".join(parts)
    raise RuntimeError(f"Could not extract text from OpenAI response: {data}")
