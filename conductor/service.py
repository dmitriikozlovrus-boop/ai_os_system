from __future__ import annotations

from datetime import date
from typing import Any

from .config import Settings
from .models import Classification, StudyItem, TaskItem
from .notion_client import NotionClient
from .openai_client import OpenAIClient
from .pending import PendingStore
from .telegram import TelegramClient
from .todoist_client import TodoistClient


class ConductorService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai = OpenAIClient(settings.openai_api_key, settings.openai_model, settings.openai_transcribe_model)
        self.notion = NotionClient(
            settings.notion_token,
            settings.notion_tasks_database_id,
            settings.notion_study_database_id,
            settings.notion_projects_database_id,
        )
        self.telegram = TelegramClient(settings.telegram_bot_token)
        self.todoist = TodoistClient(settings.todoist_api_token, settings.todoist_enabled)
        self.pending = PendingStore(settings.pending_store_path)

    def process_text(self, text: str, *, chat_id: int | None = None, source: str = "Telegram") -> dict[str, Any]:
        if chat_id is not None:
            pending = self.pending.pop_oldest_for_chat(chat_id)
            if pending:
                _, pending_item = pending
                text = _merge_pending_text(pending_item, text)
        try:
            projects = self.notion.list_projects()
        except Exception as exc:  # noqa: BLE001 - missing project context should not break capture.
            projects = []
            print(f"Could not load Notion projects: {exc}", flush=True)
        try:
            classification = self.openai.classify(text, projects=projects, today=date.today().isoformat())
        except Exception as exc:  # noqa: BLE001 - notify the user instead of returning a webhook 502.
            if chat_id is not None:
                self.telegram.send_message(chat_id, f"Не смог разобрать сообщение через AI: {exc}")
            return {"tasks_created": [], "studies_created": [], "pending": 0, "errors": [str(exc)], "notes": []}
        return self._handle_classification(classification, chat_id=chat_id, source=source)

    def process_audio(
        self,
        filename: str,
        data: bytes,
        *,
        content_type: str,
        chat_id: int | None = None,
        source: str = "Telegram voice",
    ) -> dict[str, Any]:
        text = self.openai.transcribe(filename, data, content_type)
        result = self.process_text(text, chat_id=chat_id, source=source)
        result["transcript"] = text
        return result

    def _handle_classification(
        self, classification: Classification, *, chat_id: int | None, source: str
    ) -> dict[str, Any]:
        created_tasks: list[str] = []
        created_studies: list[str] = []
        pending_count = 0
        errors: list[str] = []

        for item in classification.tasks:
            questions = self._task_questions(item)
            if questions and chat_id is not None:
                self.pending.add(chat_id, {"type": "task", "item": item.__dict__}, questions)
                pending_count += 1
                self.telegram.send_message(chat_id, _format_questions(item.title, questions))
                continue
            try:
                url = self.notion.create_task(item, source=source)
                created_tasks.append(url)
                self.todoist.create_task(item)
            except Exception as exc:  # noqa: BLE001 - notify user rather than hide automation failures.
                errors.append(f"Не удалось создать задачу '{item.title}': {exc}")

        for item in classification.studies:
            questions = self._study_questions(item)
            if questions and chat_id is not None:
                self.pending.add(chat_id, {"type": "study", "item": item.__dict__}, questions)
                pending_count += 1
                self.telegram.send_message(chat_id, _format_questions(item.question, questions))
                continue
            try:
                created_studies.append(self.notion.create_study(item))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Не удалось создать вопрос на изучение '{item.question}': {exc}")

        if chat_id is not None and errors:
            self.telegram.send_message(chat_id, "\n".join(errors))
        return {
            "tasks_created": created_tasks,
            "studies_created": created_studies,
            "pending": pending_count,
            "errors": errors,
            "notes": classification.notes,
        }

    def _task_questions(self, item: TaskItem) -> list[str]:
        questions: list[str] = []
        if item.confidence < self.settings.confidence_threshold:
            questions.append(f"Уверенность {item.confidence:.0%}. Подтверди, что это задача.")
        if "project" in item.missing or not item.project:
            questions.append("К какому проекту отнести?")
        if "due_date" in item.missing or not item.due_date:
            questions.append("Какой срок исполнения?")
        if "area" in item.missing or not item.area:
            questions.append("Какое направление: Работа, Бизнес, Личное развитие, Семья или Прочее?")
        return questions

    def _study_questions(self, item: StudyItem) -> list[str]:
        questions: list[str] = []
        if item.confidence < self.settings.confidence_threshold:
            questions.append(f"Уверенность {item.confidence:.0%}. Подтверди, что это вопрос на изучение.")
        if "project" in item.missing or not item.project:
            questions.append("К какому проекту отнести?")
        if "due_date" in item.missing or not item.due_date:
            questions.append("Какой срок/горизонт изучения?")
        if "area" in item.missing or not item.area:
            questions.append("Какое направление: Работа, Бизнес, Личное развитие, Семья или Прочее?")
        return questions


def _format_questions(title: str, questions: list[str]) -> str:
    joined = "\n".join(f"- {q}" for q in questions)
    return f"Нужно уточнение по записи:\n{title}\n\n{joined}\n\nОтветь одним сообщением, я сохраню это как уточнение для следующего шага."


def _merge_pending_text(pending_item: dict[str, Any], answer: str) -> str:
    payload = pending_item.get("payload", {})
    item = payload.get("item", {})
    questions = "\n".join(pending_item.get("questions", []))
    return (
        "Есть черновик записи Дирижера, который раньше не был сохранен из-за недостающих данных.\n"
        f"Тип черновика: {payload.get('type')}\n"
        f"Черновик: {item}\n"
        f"Какие уточнения были запрошены: {questions}\n"
        f"Ответ пользователя: {answer}\n"
        "Собери финальную запись. Если теперь данных хватает, confidence должен быть >= 0.70 и missing пустой."
    )
