from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from .http import HttpError, request_json, request_multipart
from .models import (
    AREAS,
    GOODS_CURRENCIES,
    GOODS_STATUSES,
    GOODS_TYPES,
    GOODS_USAGE_PLACES,
    GOODS_USERS,
    PROJECT_PRIORITIES,
    Classification,
    classification_from_dict,
)


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
        "goods": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "status": {
                        "type": ["string", "null"],
                        "enum": ["Не куплено", "Необходимо выбрать", "В процессе", "Необходимо одобрить выбор", "Куплено", None],
                    },
                    "goods_type": {
                        "type": ["string", "null"],
                        "enum": [
                            "Техника/электроника",
                            "Дом/быт",
                            "Одежда/обувь",
                            "Здоровье/красота",
                            "Еда/напитки",
                            "Хобби/спорт",
                            "Подарок",
                            "Другое",
                            None,
                        ],
                    },
                    "priority": {"type": ["string", "null"], "enum": ["P1", "P2", "P3", "P4", None]},
                    "price": {"type": ["number", "null"]},
                    "currency": {"type": ["string", "null"], "enum": ["MXN", "USD", "EUR", "RUB", None]},
                    "goods_user": {
                        "type": ["string", "null"],
                        "enum": ["Личное", "Семья", "Ребёнок", "Партнёр/партнёрша", "Дом", "Работа", "Подарок", "Другое", None],
                    },
                    "usage_place": {
                        "type": ["string", "null"],
                        "enum": ["Дом", "Офис", "Поездки", "Подарок", "Другое", None],
                    },
                    "stream": {
                        "type": ["string", "null"],
                        "enum": ["Работа", "Бизнес", "Личное развитие", "Семья", "Прочее", None],
                    },
                    "project": {"type": ["string", "null"]},
                    "url": {"type": ["string", "null"]},
                    "source": {"type": ["string", "null"], "enum": ["Вручную", "ИИ", None]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "missing": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "status",
                    "goods_type",
                    "priority",
                    "price",
                    "currency",
                    "goods_user",
                    "usage_place",
                    "stream",
                    "project",
                    "url",
                    "source",
                    "confidence",
                    "missing",
                ],
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tasks", "studies", "goods", "notes"],
}


class OpenAIClient:
    def __init__(self, api_key: str, model: str, transcribe_model: str, transcribe_fallback_model: str | None = None):
        self.api_key = api_key
        self.model = model
        self.transcribe_model = transcribe_model
        self.transcribe_fallback_model = transcribe_fallback_model

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def classify(self, text: str, *, projects: list[dict[str, str]], today: str) -> Classification:
        if not self.api_key:
            return self._fallback(text, today=today, projects=projects)

        project_lines = "\n".join(
            f"- {p.get('name')} | направление: {p.get('area') or 'не указано'} | статус: {p.get('status') or 'не указано'}"
            for p in projects
        )
        system = (
            "Ты классификатор сервиса 'Дирижер'. Работай строго по ТЗ:\n"
            "- Задача = любое действие кроме простого чтения/изучения.\n"
            "- Вопрос на изучение = чтение, просмотр, анализ информации или справка.\n"
            "- Goods = конкретный товар, предмет, устройство или объект, который пользователь хочет купить, выбрать, найти, заменить или учитывать.\n"
            "- Task = действие пользователя. Одно сообщение может содержать одновременно Goods и Task.\n"
            "- Запрос 'купить X' обычно содержит Goods: X и Task: купить X, если действие нужно сохранить как отдельную задачу.\n"
            "- Запрос 'нужен X' обычно содержит только Goods.\n"
            "- Запрос 'подобрать X' создает Goods со статусом 'Необходимо выбрать'.\n"
            "- Не создавай Study автоматически только потому, что товар нужно выбрать; Study нужен только при явном изучении/сравнении/анализе.\n"
            "- Не создавай Goods для абстрактной темы исследования без конкретного предмета покупки.\n"
            "- Не мельчи: объединяй близкие действия в одну сущность, если это один смысловой результат.\n"
            "- Если проект неясен, поставь project=null и добавь 'project' в missing.\n"
            "- Если срок не указан, поставь due_date=null и добавь 'due_date' в missing.\n"
            "- Если уверенность по проекту/типу/сроку ниже 0.70, добавь соответствующее поле в missing.\n"
            "- В title задачи не включай проект, направление, срок, оценку времени и желаемый результат; title = только короткое действие.\n"
            "- Title задачи всегда начинай с большой буквы.\n"
            "- В question вопроса на изучение не включай проект, направление, срок и формат результата; question = только что именно изучаем.\n"
            "- Question вопроса на изучение начинай с большой буквы и по возможности убирай стартовые глаголы вроде 'изучить', 'исследовать', 'разобрать'.\n"
            "- По умолчанию research_type = 'Простое'. Только если пользователь явно просит глубокое/подробное исследование, ставь 'Глубокое'.\n"
            "- По умолчанию result_format = 'Краткая справка'. Если research_type = 'Глубокое', то result_format = 'Подробная справка'.\n"
            "- desired_result формулируй как завершенный артефакт или завершенное действие: 'Подготовленная справка', 'Совершенный звонок', 'Отправленное письмо'.\n"
            "- effort_minutes оценивай консервативно, как среднюю трудозатратность специалиста уровня 4 из 10.\n"
            "- industry определи коротким названием отрасли.\n"
            "- Для Goods используй source='ИИ', status='Не куплено' по умолчанию; если пользователь просит подобрать или выбрать товар, status='Необходимо выбрать'.\n"
            "- Для Goods не придумывай priority, price, currency, goods_user, usage_place, stream, project или url.\n"
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
        try:
            data = request_json(
                "POST",
                "https://api.openai.com/v1/responses",
                headers={**self.headers, "Content-Type": "application/json"},
                payload=payload,
                timeout=90,
            )
        except HttpError as exc:
            if exc.status in {429, 500, 502, 503, 504}:
                return self._fallback(
                    text,
                    today=today,
                    projects=projects,
                    note=f"fallback classifier after OpenAI HTTP {exc.status}",
                )
            raise
        raw = _extract_response_text(data)
        classification = classification_from_dict(json.loads(raw))
        return _postprocess_classification(classification, projects=projects)

    def transcribe(self, filename: str, data: bytes, content_type: str = "audio/ogg") -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for voice transcription")
        errors: list[str] = []
        for model in self._transcription_models():
            try:
                response = request_multipart(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=self.headers,
                    fields={"model": model, "response_format": "json", "language": "ru"},
                    files={"file": (filename, data, content_type)},
                    timeout=120,
                )
                text = str(response.get("text") or "").strip()
                if text:
                    return text
                errors.append(f"{model}: empty transcript")
            except Exception as exc:  # noqa: BLE001 - we want to try the backup model before failing.
                errors.append(f"{model}: {exc}")
        raise RuntimeError(" ; ".join(errors) if errors else "voice transcription failed")

    def _transcription_models(self) -> list[str]:
        models = [self.transcribe_model]
        if self.transcribe_fallback_model and self.transcribe_fallback_model not in models:
            models.append(self.transcribe_fallback_model)
        return models

    def _fallback(
        self,
        text: str,
        *,
        today: str | None = None,
        projects: list[dict[str, str]] | None = None,
        note: str = "fallback classifier",
    ) -> Classification:
        task_words = (
            "позвон",
            "напиш",
            "напис",
            "найти",
            "посчит",
            "подготов",
            "договор",
            "сдел",
            "отправ",
            "напом",
            "купить",
            "приобрести",
            "заказать",
        )
        study_words = ("изуч", "разобраться в", "исслед", "собрать справ")
        goods_words = (
            "купить",
            "нужен",
            "нужна",
            "нужно приобрести",
            "подобрать",
            "подбери",
            "выбрать",
            "выбери",
            "заказать",
            "закажи",
        )
        lower = text.lower()
        data: dict[str, Any] = {"tasks": [], "studies": [], "goods": [], "notes": [note]}
        task_text, study_text = _split_task_and_study(text)
        if any(word in lower for word in task_words):
            source = task_text or text
            project = _extract_after(source, r"по проекту\s+([^,.]+)")
            area = _extract_after(source, r"направлени[ея]\s+([^,.]+)")
            due_date = _extract_due_date(source, today)
            effort_minutes = _extract_minutes(source) or _infer_effort_minutes(source)
            desired_result = _extract_after(source, r"Желаемый результат:\s*([^.\n]+)") or _infer_desired_result(source)
            data["tasks"].append(
                {
                    "title": _clean_title(source, prefixes=("юба, задача:", "люба, задача:", "задача:"), kind="task"),
                    "description": source,
                    "desired_result": desired_result,
                    "project": project,
                    "area": _normalize_area(area),
                    "due_date": due_date,
                    "effort_minutes": effort_minutes,
                    "priority": "P2",
                    "next_step": _first_sentence(source),
                    "confidence": 0.75 if project and due_date else 0.45,
                    "missing": _missing(project=project, area=_normalize_area(area), due_date=due_date),
                }
            )
        if study_text or any(word in lower for word in study_words):
            source = study_text or text
            project = _extract_after(source, r"по проекту\s+([^,.]+)")
            area = _extract_after(source, r"направлени[ея]\s+([^,.]+)")
            due_date = _extract_due_date(source, today)
            research_type = "Глубокое" if _wants_deep_research(source) else "Простое"
            data["studies"].append(
                {
                    "question": _clean_title(source, prefixes=("и на изучение:", "на изучение:"), kind="study"),
                    "description": source,
                    "industry": _guess_industry(source),
                    "research_type": research_type,
                    "project": project,
                    "area": _normalize_area(area),
                    "priority": "P2",
                    "result_format": "Подробная справка" if research_type == "Глубокое" else "Краткая справка",
                    "due_date": due_date,
                    "source": "Telegram",
                    "confidence": 0.75 if project and due_date else 0.45,
                    "missing": _missing(project=project, area=_normalize_area(area), due_date=due_date),
                }
            )
        if any(word in lower for word in goods_words):
            price, currency = _extract_price_and_currency(text)
            status = (
                "Необходимо выбрать"
                if any(word in lower for word in ("подобрать", "подбери", "выбрать", "выбери"))
                else "Не куплено"
            )
            data["goods"].append(
                {
                    "title": _extract_goods_title(text),
                    "status": status,
                    "goods_type": _infer_goods_type(text),
                    "priority": None,
                    "price": price,
                    "currency": currency,
                    "goods_user": _infer_goods_user(text),
                    "usage_place": _infer_usage_place(text),
                    "stream": _extract_goods_stream(text),
                    "project": _extract_after(text, r"по проекту\s+([^,.]+)"),
                    "url": _extract_url(text),
                    "source": "ИИ",
                    "confidence": 0.8,
                    "missing": [],
                }
            )
        classification = classification_from_dict(data)
        return _postprocess_classification(classification, projects=projects or [])


def _split_task_and_study(text: str) -> tuple[str, str]:
    marker = re.search(r"\b(?:и\s+)?на изучение\s*:", text, flags=re.IGNORECASE)
    if not marker:
        return text, ""
    return text[: marker.start()].strip(), text[marker.start() :].strip()


def _extract_after(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_minutes(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:минут|мин|м\b)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_price_and_currency(text: str) -> tuple[float | None, str | None]:
    match = re.search(r"(\d+(?:[\s.,]\d{3})*(?:[.,]\d+)?)\s*(MXN|USD|EUR|RUB)?", text, flags=re.IGNORECASE)
    if not match:
        return None, None
    raw = match.group(1).replace(" ", "")
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".") if len(raw.rsplit(",", 1)[-1]) != 3 else raw.replace(",", "")
    else:
        raw = raw.replace(",", "")
    try:
        price = float(raw)
    except ValueError:
        return None, None
    if price < 0:
        return None, None
    currency = match.group(2).upper() if match.group(2) else None
    return price, currency if currency in GOODS_CURRENCIES else None


def _extract_url(text: str) -> str | None:
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(".,)") if match else None


def _extract_due_date(text: str, today: str | None) -> str | None:
    if not today:
        return None
    base = date.fromisoformat(today)
    lower = text.lower()
    if "послезавтра" in lower:
        return (base + timedelta(days=2)).isoformat()
    if "завтра" in lower:
        return (base + timedelta(days=1)).isoformat()
    weekdays = {
        "понедельник": 0,
        "вторник": 1,
        "сред": 2,
        "четверг": 3,
        "пятниц": 4,
        "суббот": 5,
        "воскрес": 6,
    }
    for word, weekday in weekdays.items():
        if word in lower:
            delta = (weekday - base.weekday()) % 7
            return (base + timedelta(days=delta or 7)).isoformat()
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    return match.group(1) if match else None


def _normalize_area(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().capitalize()
    aliases = {"Личное": "Личное развитие"}
    return aliases.get(cleaned, cleaned)


def _missing(*, project: str | None, area: str | None, due_date: str | None) -> list[str]:
    missing = []
    if not project:
        missing.append("project")
    if not area:
        missing.append("area")
    if not due_date:
        missing.append("due_date")
    return missing


def _clean_title(text: str, *, prefixes: tuple[str, ...], kind: str = "generic") -> str:
    value = text.strip()
    lower = value.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            value = value[len(prefix) :].strip()
            break
    value = _strip_metadata_from_title(value, kind=kind)
    return _capitalize_first_letter(_first_sentence(value)[:120])


def _extract_goods_title(text: str) -> str:
    value = text.strip()
    replacements = (
        r"^\s*(?:люба,\s*)?(?:нужен|нужна|нужно приобрести|купить|подобрать|подбери|выбрать|выбери|заказать|закажи)\s+",
    )
    for pattern in replacements:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+до\s+\d+(?:[\s.,]\d{3})*(?:[.,]\d+)?\s*(?:MXN|USD|EUR|RUB)?", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+по проекту\s+[^,.]+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+направлени[ея]\s+[^,.]+", "", value, flags=re.IGNORECASE)
    value = _extract_url(value) and value.replace(_extract_url(value) or "", "") or value
    return _capitalize_first_letter(_first_sentence(value).strip(" .,\n\t")[:120])


def _strip_metadata_from_title(text: str, *, kind: str) -> str:
    value = text.strip()
    metadata_patterns = [
        r"\s+по проекту\s+[^,.]+",
        r"\s+направлени[ея]\s+[^,.]+",
        r"\s+оценка\s+\d+\s*(?:минут|мин|м\b|час[а-я]*)",
        r"\s+желаемый результат\s*:\s*.+$",
        r"\s+нужна\s+.+(?:справка|таблица|memo|дайджест).*$",
    ]
    for pattern in metadata_patterns:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE)
    if kind == "task":
        value = re.sub(r"^(?:до\s+\S+\s+)", "", value, flags=re.IGNORECASE)
    if kind == "study":
        value = re.sub(r"^(?:до\s+\S+\s+)", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^(?:изучить|исследовать|разобрать|разобраться в|понять)\s+", "", value, flags=re.IGNORECASE)
    return value.strip(" .,\n\t")


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0][:200]


def _capitalize_first_letter(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1 :]
    return text


def _guess_industry(text: str) -> str:
    lower = text.lower()
    if "логист" in lower or "веракрус" in lower:
        return "Логистика"
    if "алюмин" in lower or "сыр" in lower:
        return "Сырьевые товары"
    if "ai" in lower or "ии" in lower:
        return "AI"
    return "Не определено"


def _infer_effort_minutes(text: str) -> int:
    lower = text.lower()
    if any(word in lower for word in ("позвон", "напис", "ответ", "отправ")):
        return 15
    if any(word in lower for word in ("подготов", "собрать", "соглас", "сравн")):
        return 30
    if any(word in lower for word in ("переговор", "рассчитать", "разобраться", "проработ")):
        return 60
    return 30


def _infer_desired_result(text: str) -> str:
    lower = text.lower()
    if "рожд" in lower and ("напом" in lower or "поздрав" in lower):
        return "Совершенное поздравление"
    if "позвон" in lower:
        return "Совершенный звонок"
    if "напис" in lower or "отправ" in lower:
        return "Отправленное письмо"
    if "подготов" in lower and "справ" in lower:
        return "Подготовленная справка"
    if "подготов" in lower:
        return "Подготовленный материал"
    if "собрать" in lower:
        return "Собранная информация"
    return "Выполненная задача"


def _wants_deep_research(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in ("глубок", "подроб", "детальн", "развернут"))


def _infer_goods_type(text: str) -> str | None:
    lower = text.lower()
    if any(word in lower for word in ("ноутбук", "телефон", "планшет", "компьютер", "наушник", "гаджет")):
        return "Техника/электроника"
    if any(word in lower for word in ("диван", "стол", "стул", "ламп", "пылесос", "кухн")):
        return "Дом/быт"
    if any(word in lower for word in ("ботин", "кроссов", "куртк", "рубаш", "плать", "обув")):
        return "Одежда/обувь"
    if any(word in lower for word in ("витамин", "крем", "шампун", "лекар")):
        return "Здоровье/красота"
    if any(word in lower for word in ("кофе", "чай", "еда", "напит")):
        return "Еда/напитки"
    if any(word in lower for word in ("спорт", "велосипед", "гантел", "хобби")):
        return "Хобби/спорт"
    if "подар" in lower:
        return "Подарок"
    return None


def _infer_goods_user(text: str) -> str | None:
    lower = text.lower()
    if "реб" in lower or "сын" in lower or "доч" in lower:
        return "Ребёнок"
    if "подар" in lower:
        return "Подарок"
    if "для дома" in lower:
        return "Дом"
    if "для работы" in lower:
        return "Работа"
    if "для семьи" in lower:
        return "Семья"
    return None


def _infer_usage_place(text: str) -> str | None:
    lower = text.lower()
    if "для дома" in lower or "домой" in lower:
        return "Дом"
    if "для офиса" in lower or "в офис" in lower:
        return "Офис"
    if "поезд" in lower or "дорог" in lower:
        return "Поездки"
    if "подар" in lower:
        return "Подарок"
    return None


def _extract_goods_stream(text: str) -> str | None:
    return _normalize_area(_extract_after(text, r"(?:стрим|направлени[ея])\s+([^,.]+)"))


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


def _postprocess_classification(classification: Classification, *, projects: list[dict[str, str]]) -> Classification:
    project_map = {
        str(project.get("name") or "").strip().casefold(): project
        for project in projects
        if str(project.get("name") or "").strip()
    }

    for item in classification.tasks:
        item.title = _clean_title(item.title or item.description, prefixes=(), kind="task")
        item.title = _normalize_birthday_task_title(item.title, item.description)
        item.desired_result = item.desired_result or _infer_desired_result(item.description or item.title)
        item.area = _normalize_area(item.area)
        matched_project = _match_project(item.project, project_map)
        if matched_project:
            item.project = matched_project["name"]
            if not item.area:
                item.area = _normalize_area(matched_project.get("area"))
        elif item.project and project_map:
            item.project = None
            _ensure_missing(item.missing, "project")
        _ensure_missing(item.missing, "due_date", when=not item.due_date)
        _ensure_missing(item.missing, "project", when=not item.project)
        _ensure_missing(item.missing, "area", when=not item.area)

    for item in classification.studies:
        item.question = _clean_title(item.question or item.description, prefixes=(), kind="study")
        item.industry = item.industry or _guess_industry(item.description or item.question)
        item.research_type = item.research_type if item.research_type in {"Простое", "Глубокое"} else "Простое"
        if item.result_format not in RESULT_FORMAT_HINTS:
            item.result_format = "Подробная справка" if item.research_type == "Глубокое" else "Краткая справка"
        if item.research_type == "Простое" and item.result_format == "Подробная справка":
            item.result_format = "Краткая справка"
        if item.research_type == "Глубокое" and item.result_format == "Краткая справка":
            item.result_format = "Подробная справка"
        item.area = _normalize_area(item.area)
        matched_project = _match_project(item.project, project_map)
        if matched_project:
            item.project = matched_project["name"]
            if not item.area:
                item.area = _normalize_area(matched_project.get("area"))
        elif item.project and project_map:
            item.project = None
            _ensure_missing(item.missing, "project")
        _ensure_missing(item.missing, "due_date", when=not item.due_date)
        _ensure_missing(item.missing, "project", when=not item.project)
        _ensure_missing(item.missing, "area", when=not item.area)

    for item in classification.goods:
        item.title = _clean_title(item.title, prefixes=(), kind="goods")
        item.status = item.status if item.status in GOODS_STATUSES else "Не куплено"
        item.goods_type = item.goods_type if item.goods_type in GOODS_TYPES else None
        item.priority = item.priority if item.priority in PROJECT_PRIORITIES else None
        if item.price is not None and item.price < 0:
            item.price = None
        item.currency = item.currency if item.currency in GOODS_CURRENCIES else None
        item.goods_user = item.goods_user if item.goods_user in GOODS_USERS else None
        item.usage_place = item.usage_place if item.usage_place in GOODS_USAGE_PLACES else None
        item.stream = _normalize_area(item.stream)
        if item.stream not in AREAS:
            item.stream = None
        item.url = item.url if _valid_url(item.url) else None
        item.source = "ИИ"
        matched_project = _match_project(item.project, project_map)
        if matched_project:
            item.project = matched_project["name"]
        elif item.project and project_map:
            item.project = None
        _ensure_missing(item.missing, "title", when=not item.title)

    return classification


RESULT_FORMAT_HINTS = {"Краткая справка", "Подробная справка", "Memo", "Таблица", "Telegram-дайджест"}


def _match_project(value: str | None, project_map: dict[str, dict[str, str]]) -> dict[str, str] | None:
    if not value:
        return None
    return project_map.get(value.strip().casefold())


def _ensure_missing(missing: list[str], field: str, *, when: bool = True) -> None:
    if when:
        if field not in missing:
            missing.append(field)
        return
    if field in missing:
        missing[:] = [value for value in missing if value != field]


def _valid_url(value: str | None) -> bool:
    return bool(value and re.match(r"^https?://[^\s]+$", value))


def _normalize_birthday_task_title(title: str, description: str) -> str:
    combined = f"{title} {description}".lower()
    if "рожд" not in combined:
        return title
    normalized = title.strip()
    lower = normalized.lower()
    for prefix in ("завтра ", "сегодня ", "послезавтра "):
        if lower.startswith(prefix):
            normalized = normalized[len(prefix) :]
            lower = normalized.lower()
            break
    if lower.startswith("напомнить "):
        normalized = "Поздравить " + normalized[len("напомнить ") :]
    elif lower.startswith("напомни "):
        normalized = "Поздравить " + normalized[len("напомни ") :]
    normalized = re.sub(r"\bо дне рождения\b", "с днем рождения", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bпро день рождения\b", "с днем рождения", normalized, flags=re.IGNORECASE)
    return _capitalize_first_letter(normalized.strip())
