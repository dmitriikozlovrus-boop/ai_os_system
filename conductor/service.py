from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from .config import Settings
from .interactions import InteractionStore
from .models import Classification, GoodsItem, StudyItem, SystemIssueRecord, TaskItem
from .notion_client import NotionClient
from .openai_client import OpenAIClient, _extract_due_date, _normalize_area
from .pending import PendingStore
from .recent import RecentStore
from .telegram import TelegramClient
from .todoist_client import TodoistClient
from .task_sync import TaskSyncService


class ConductorService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai = OpenAIClient(
            settings.openai_api_key,
            settings.openai_model,
            settings.openai_transcribe_model,
            settings.openai_transcribe_fallback_model,
        )
        self.notion = NotionClient(
            token=settings.notion_token,
            tasks_db=settings.notion_tasks_database_id,
            study_db=settings.notion_study_database_id,
            projects_db=settings.notion_projects_database_id,
            goods_db=settings.notion_goods_database_id,
            system_issues_db=settings.notion_system_issues_database_id,
        )
        self.telegram = TelegramClient(settings.telegram_bot_token)
        # A configured token is enough to enable the client. The dedicated
        # TODOIST_SYNC_PAUSED flag is the single operational kill switch.
        self.todoist = TodoistClient(settings.todoist_api_token, settings.todoist_enabled or bool(settings.todoist_api_token))
        self.task_sync = TaskSyncService(
            settings.notion_token,
            settings.notion_tasks_database_id,
            settings.notion_projects_database_id,
            self.todoist,
            settings.todoist_sync_state_path,
            settings.todoist_completed_since,
            settings.notion_streams_database_id,
            paused=settings.todoist_sync_paused,
            # The legacy production value is still "observe" in Render.
            # Migrate it to the webhook-only Todoist-primary mode; all bulk
            # Todoist write flags remain disabled.
            mode="todoist-primary" if settings.todoist_sync_mode == "observe" else settings.todoist_sync_mode,
            allow_project_create=settings.todoist_allow_project_create,
            allow_task_create=settings.todoist_allow_task_create,
            allow_task_move=settings.todoist_allow_task_move,
            allow_label_write=settings.todoist_allow_label_write,
            allow_status_write=settings.todoist_allow_status_write,
            allow_missing_cancel=settings.todoist_allow_missing_cancel,
            max_task_moves=settings.todoist_max_task_moves,
            snapshot_path=settings.todoist_snapshot_path,
        )
        self.pending = PendingStore(settings.pending_store_path)
        self.recent = RecentStore(settings.recent_store_path)
        self.interactions = InteractionStore(settings.interaction_store_path)

    def process_text(
        self,
        text: str,
        *,
        chat_id: int | None = None,
        source: str = "Telegram",
        telegram_message_id: int | None = None,
        reply_to_message_id: int | None = None,
        skip_feedback: bool = False,
    ) -> dict[str, Any]:
        if chat_id is not None and not skip_feedback and hasattr(self, "interactions"):
            feedback = self.interactions.get_feedback(chat_id)
            if feedback:
                return self._handle_feedback_followup(text, chat_id=chat_id, source=source, feedback=feedback)
            reply_interaction = self.interactions.find_by_reply(chat_id, reply_to_message_id)
            latest_interaction = self.interactions.latest_for_chat(chat_id)
            if reply_interaction and _looks_like_feedback(text, has_context=True, is_reply=True):
                return self._capture_feedback(
                    text,
                    chat_id=chat_id,
                    source=source,
                    interaction=reply_interaction,
                    command=text,
                )
            if _looks_like_feedback_command(text):
                return self._start_feedback_flow(text, chat_id=chat_id, reply_to_message_id=reply_to_message_id)
            if _looks_like_feedback(text, has_context=bool(latest_interaction), is_reply=False):
                if latest_interaction:
                    return self._capture_feedback(
                        text,
                        chat_id=chat_id,
                        source=source,
                        interaction=latest_interaction,
                        command=text,
                    )
                return self._start_feedback_flow(text, chat_id=chat_id, reply_to_message_id=None, no_context=True)

        interaction_id = None
        if chat_id is not None and hasattr(self, "interactions"):
            interaction_id = self.interactions.create(
                chat_id,
                text=text,
                telegram_message_id=telegram_message_id,
                reply_to_message_id=reply_to_message_id,
                model=self.settings.openai_model,
            )

        pending_item: dict[str, Any] | None = None
        if chat_id is not None:
            pending = self.pending.pop_oldest_for_chat(chat_id)
            if pending:
                _, pending_item = pending
        if chat_id is not None and not pending_item and _looks_like_edit_request(text):
            return self._handle_edit_request(text, chat_id=chat_id)
        try:
            projects = self.notion.list_projects()
        except Exception as exc:  # noqa: BLE001 - missing project context should not break capture.
            projects = []
            print(f"Could not load Notion projects: {exc}", flush=True)
        if pending_item:
            resolved = _resolve_pending_without_ai(pending_item, text, today=date.today().isoformat(), projects=projects)
            if resolved:
                return self._handle_classification(
                    resolved,
                    chat_id=chat_id,
                    source=source,
                    projects=projects,
                    from_clarification=True,
                    interaction_id=interaction_id,
                    input_text=text,
                )
            text = _merge_pending_text(pending_item, text)
        try:
            classification = self.openai.classify(text, projects=projects, today=date.today().isoformat())
        except Exception as exc:  # noqa: BLE001 - notify the user instead of returning a webhook 502.
            self._record_automatic_issue(
                "OpenAI failure",
                input_text=text,
                errors=[str(exc)],
                interaction_id=interaction_id,
            )
            if chat_id is not None:
                self._send_message(chat_id, f"Не смог разобрать сообщение через AI: {exc}", interaction_id=interaction_id)
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": []}
        if pending_item:
            classification = _apply_clarification_fallbacks(classification)
        if interaction_id:
            self.interactions.update(interaction_id, classification=_classification_payload(classification), status="classified")
        return self._handle_classification(
            classification,
            chat_id=chat_id,
            source=source,
            projects=projects,
            from_clarification=bool(pending_item),
            interaction_id=interaction_id,
            input_text=text,
        )

    def process_audio(
        self,
        filename: str,
        data: bytes,
        *,
        content_type: str,
        chat_id: int | None = None,
        source: str = "Telegram voice",
    ) -> dict[str, Any]:
        try:
            text = self.openai.transcribe(filename, data, content_type)
        except Exception as exc:  # noqa: BLE001 - voice failures should be visible to the user.
            if chat_id is not None:
                self._send_message(
                    chat_id,
                    f"Не смогла расшифровать голосовое: {exc}. Пока можно прислать текстом, а я продолжу разбор.",
                )
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": []}
        result = self.process_text(text, chat_id=chat_id, source=source)
        result["transcript"] = text
        return result

    def _handle_edit_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        recent = self.recent.get(chat_id)
        if not recent:
            self._send_message(chat_id, _edit_guidance_message())
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["edit guidance sent"]}
        try:
            projects = self.notion.list_projects()
        except Exception as exc:  # noqa: BLE001
            projects = []
            print(f"Could not load Notion projects: {exc}", flush=True)

        updated = _apply_edit_to_recent(recent, text, today=date.today().isoformat(), projects=projects)
        if not updated:
            self._send_message(chat_id, _edit_guidance_message())
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["edit guidance sent"]}

        try:
            if updated["type"] == "task":
                item = TaskItem(**updated["item"])
                self.notion.update_task(updated["page_id"], item, projects=projects)
                classification = Classification(tasks=[item], studies=[], notes=["edited recent task"])
            else:
                item = StudyItem(**updated["item"])
                self.notion.update_study(updated["page_id"], item)
                classification = Classification(tasks=[], studies=[item], notes=["edited recent study"])
        except Exception as exc:  # noqa: BLE001
            self._send_message(chat_id, f"Не смогла обновить запись: {exc}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["edit failed"]}
        self.recent.save(chat_id, updated)
        self._send_message(chat_id, _format_updated_summary(classification))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": classification.notes}

    def _handle_classification(
        self,
        classification: Classification,
        *,
        chat_id: int | None,
        source: str,
        projects: list[dict[str, str]] | None = None,
        from_clarification: bool = False,
        interaction_id: str | None = None,
        input_text: str = "",
    ) -> dict[str, Any]:
        created_tasks: list[str] = []
        created_studies: list[str] = []
        created_goods: list[str] = []
        created_task_items: list[TaskItem] = []
        created_study_items: list[StudyItem] = []
        created_goods_items: list[GoodsItem] = []
        pending_count = 0
        errors: list[str] = []

        for item in classification.tasks:
            questions = self._task_questions(item)
            if questions and chat_id is not None:
                self.pending.add(chat_id, {"type": "task", "item": item.__dict__}, questions)
                if interaction_id:
                    self.interactions.append(interaction_id, "pending", {"type": "task", "item": item.__dict__})
                    self.interactions.append(interaction_id, "questions", questions)
                pending_count += 1
                self._send_message(chat_id, _format_questions(item.title, questions), interaction_id=interaction_id)
                continue
            try:
                url = self.notion.create_task(item, source=source, projects=projects)
                created_tasks.append(url)
                created_task_items.append(item)
                if chat_id is not None:
                    self.recent.save(chat_id, _recent_payload("task", url, item.__dict__))
            except Exception as exc:  # noqa: BLE001 - notify user rather than hide automation failures.
                errors.append(f"Не удалось создать задачу '{item.title}': {exc}")

        for item in classification.studies:
            questions = self._study_questions(item)
            if questions and chat_id is not None:
                self.pending.add(chat_id, {"type": "study", "item": item.__dict__}, questions)
                if interaction_id:
                    self.interactions.append(interaction_id, "pending", {"type": "study", "item": item.__dict__})
                    self.interactions.append(interaction_id, "questions", questions)
                pending_count += 1
                self._send_message(chat_id, _format_questions(item.question, questions), interaction_id=interaction_id)
                continue
            try:
                url = self.notion.create_study(item)
                created_studies.append(url)
                created_study_items.append(item)
                if chat_id is not None:
                    self.recent.save(chat_id, _recent_payload("study", url, item.__dict__))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Не удалось создать вопрос на изучение '{item.question}': {exc}")

        for item in classification.goods:
            questions = self._goods_questions(item)
            if questions and chat_id is not None:
                self.pending.add(chat_id, {"type": "goods", "item": item.__dict__}, questions)
                if interaction_id:
                    self.interactions.append(interaction_id, "pending", {"type": "goods", "item": item.__dict__})
                    self.interactions.append(interaction_id, "questions", questions)
                pending_count += 1
                self._send_message(chat_id, _format_questions(item.title or "Товар", questions), interaction_id=interaction_id)
                continue
            try:
                url = self.notion.create_goods(item, projects=projects)
                created_goods.append(url)
                created_goods_items.append(item)
                if chat_id is not None:
                    self.recent.save(chat_id, _recent_payload("goods", url, item.__dict__))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Не удалось создать товар '{item.title}': {exc}")

        if chat_id is not None and errors:
            self._send_message(chat_id, "\n".join(errors), interaction_id=interaction_id)
        if chat_id is not None and (created_tasks or created_studies or created_goods):
            created_classification = Classification(
                tasks=created_task_items,
                studies=created_study_items,
                goods=created_goods_items,
                notes=classification.notes,
            )
            self._send_message(chat_id, _format_created_summary(created_classification, from_clarification=from_clarification), interaction_id=interaction_id)
        if interaction_id:
            self.interactions.update(
                interaction_id,
                created={"tasks": created_tasks, "studies": created_studies, "goods": created_goods},
                errors=errors,
                status="completed_with_errors" if errors else "completed",
            )
        if errors:
            self._record_automatic_issue("Partial write" if (created_tasks or created_studies or created_goods) else "Notion failure", input_text=input_text, errors=errors, interaction_id=interaction_id)
        return {
            "tasks_created": created_tasks,
            "studies_created": created_studies,
            "goods_created": created_goods,
            "pending": pending_count,
            "errors": errors,
            "notes": classification.notes,
        }

    def _start_feedback_flow(
        self,
        command: str,
        *,
        chat_id: int,
        reply_to_message_id: int | None,
        no_context: bool = False,
    ) -> dict[str, Any]:
        interaction = self.interactions.find_by_reply(chat_id, reply_to_message_id) or self.interactions.latest_for_chat(chat_id)
        if no_context or not interaction:
            self.interactions.start_feedback(chat_id, command=command, interaction=None, state="awaiting_orphan_correction")
            self._send_message(chat_id, _feedback_no_context_prompt())
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback context requested"]}
        self.interactions.start_feedback(chat_id, command=command, interaction=interaction)
        self._send_message(chat_id, _feedback_prompt())
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback correction requested"]}

    def _capture_feedback(
        self,
        correction: str,
        *,
        chat_id: int,
        source: str,
        interaction: dict[str, Any],
        command: str,
    ) -> dict[str, Any]:
        issue = self._build_system_issue(
            command=command,
            correction=correction.strip(),
            interaction=interaction,
            detection_method="Пользователь",
        )
        errors: list[str] = []
        try:
            issue_url = self.notion.create_system_issue(issue)
        except Exception as exc:  # noqa: BLE001
            print(f"ISSUE_CAPTURE_ERROR feedback: {exc}", flush=True)
            errors.append(str(exc))
            self._send_message(chat_id, f"Не смогла сохранить ошибку в SYSTEM ISSUES: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": errors, "notes": ["feedback issue save failed"]}

        if issue.classification.needs_user_clarification:
            self.interactions.start_feedback(chat_id, command=command, interaction=interaction, state="awaiting_correction")
            self._send_message(chat_id, _format_issue_needs_clarification(issue))
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback clarification requested"], "issue_url": issue_url}

        feedback = {
            "state": "awaiting_fix_confirmation",
            "command": command,
            "correction": correction.strip(),
            "interaction": interaction,
            "issue": _issue_payload(issue),
            "issue_url": issue_url,
        }
        self.interactions.update_feedback(chat_id, feedback)
        self._send_message(chat_id, _format_issue_saved(issue))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback issue saved"], "issue_url": issue_url}

    def _handle_feedback_followup(
        self,
        text: str,
        *,
        chat_id: int,
        source: str,
        feedback: dict[str, Any],
    ) -> dict[str, Any]:
        state = feedback.get("state")
        if state == "awaiting_fix_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_yes(text):
                original = str((feedback.get("interaction") or {}).get("input_text") or "")
                correction = str(feedback.get("correction") or "")
                merged = f"{original}\n\nИсправление пользователя: {correction}".strip()
                result = self.process_text(merged, chat_id=chat_id, source=source, skip_feedback=True)
                if not result.get("errors") and feedback.get("issue_url"):
                    try:
                        self.notion.update_system_issue(
                            _extract_notion_page_id(str(feedback["issue_url"])),
                            solution="Запись исправлена через Telegram feedback flow",
                            status="В анализе",
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"ISSUE_CAPTURE_ERROR update: {exc}", flush=True)
                self._send_message(chat_id, _format_fix_completed(result))
                return result
            self._send_message(chat_id, "Хорошо, запись сейчас не исправляю.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback fix declined"]}

        interaction = feedback.get("interaction") or {}
        return self._capture_feedback(
            text,
            chat_id=chat_id,
            source=source,
            interaction=interaction,
            command=str(feedback.get("command") or ""),
        )

    def _build_system_issue(
        self,
        *,
        command: str,
        correction: str,
        interaction: dict[str, Any],
        detection_method: str,
    ) -> SystemIssueRecord:
        original = str(interaction.get("input_text") or "")
        actual_context = {
            "classification": interaction.get("classification"),
            "created": interaction.get("created"),
            "pending": interaction.get("pending"),
            "questions": interaction.get("questions"),
            "errors": interaction.get("errors"),
        }
        classification = self.openai.classify_system_issue(
            original_text=original,
            actual_context=actual_context,
            command=command,
            correction=correction,
        )
        input_data = _format_issue_input(original, interaction, command, correction)
        description = _format_issue_description(classification, interaction)
        solution = "Требуется анализ и исправление"
        if correction:
            solution += f"\n\nОжидаемое исправление:\n{correction}"
        fingerprint = _fingerprint(detection_method, classification.issue_type, classification.database, original, correction)
        return SystemIssueRecord(
            classification=classification,
            detection_method=detection_method,
            status="Новая",
            input_data=input_data,
            description=description,
            solution=solution,
            detected_date=date.today().isoformat(),
            fingerprint=fingerprint,
        )

    def _record_automatic_issue(
        self,
        title: str,
        *,
        input_text: str,
        errors: list[str],
        interaction_id: str | None,
    ) -> None:
        fingerprint = _fingerprint("Дирижёр", title, "Другое", input_text, "\n".join(errors))
        if not hasattr(self, "interactions"):
            return
        if self.interactions.has_issue_fingerprint(fingerprint):
            return
        interaction = {"input_text": input_text, "errors": errors}
        issue = self._build_system_issue(command=title, correction="\n".join(errors), interaction=interaction, detection_method="Дирижёр")
        issue.fingerprint = fingerprint
        try:
            self.notion.create_system_issue(issue)
            self.interactions.remember_issue_fingerprint(fingerprint)
            if interaction_id:
                self.interactions.append(interaction_id, "system_issues", {"fingerprint": fingerprint, "title": title})
        except Exception as exc:  # noqa: BLE001
            print(f"PRIMARY_ERROR {title}: {'; '.join(errors)}", flush=True)
            print(f"ISSUE_CAPTURE_ERROR automatic: {exc}", flush=True)
            if interaction_id:
                self.interactions.append(interaction_id, "errors", f"Could not record system issue: {exc}")

    def _send_message(self, chat_id: int, text: str, *, interaction_id: str | None = None) -> None:
        result = self.telegram.send_message(chat_id, text)
        if interaction_id and hasattr(self, "interactions"):
            self.interactions.append(interaction_id, "bot_messages", text)
            message_id = _extract_telegram_message_id(result)
            if message_id is not None:
                self.interactions.append(interaction_id, "bot_message_ids", message_id)

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
        if _needs_study_questions(item):
            questions.append("Какие именно вопросы должны войти в исследование?")
        return questions

    def _goods_questions(self, item: GoodsItem) -> list[str]:
        questions: list[str] = []
        if item.confidence < self.settings.confidence_threshold:
            questions.append("Это товар для покупки/выбора?")
        if "title" in item.missing or not item.title:
            questions.append("Какой товар или предмет нужно сохранить?")
        return questions


def _format_questions(title: str, questions: list[str]) -> str:
    joined = "\n".join(f"- {q}" for q in questions)
    return f"Нужно уточнение по записи:\n{title}\n\n{joined}\n\nОтветь одним сообщением, я сохраню это как уточнение для следующего шага."


def _looks_like_feedback_command(text: str) -> bool:
    normalized = text.strip().casefold()
    return normalized in {"неправильно", "неверно", "ошибка", "не так", "/wrong", "/error"}


def _looks_like_feedback(text: str, *, has_context: bool, is_reply: bool) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    if not normalized:
        return False
    if _looks_like_feedback_command(normalized):
        return True
    if normalized in {"да", "нет", "хорошо", "завтра"} or re.fullmatch(r"\d{1,2}:\d{2}", normalized):
        return False
    false_positive_patterns = (
        r"^ошибка\s+\S+",
        r"^книга\s+называется",
        r"^изучи\s+ошиб",
        r"^купить\s+книг",
        r"^встреча\s+не\s+так\s+важна",
    )
    if any(re.search(pattern, normalized) for pattern in false_positive_patterns):
        return False
    correction_patterns = (
        r"^нет,\s*это\s+",
        r"^это\s+не\s+.+,\s*это\s+",
        r"^нужно было\s+",
        r"^правильно будет\s*:",
        r"^ничего создавать не ",
        r"^не нужно было\s+",
        r"^дата\s+(?:неверная|не та|должна)",
        r"^время\s+(?:неверное|не то|должно)",
        r"^поставь\s+время",
        r"^это для проекта\s+",
        r"^ты не создал",
        r"^ты не создала",
        r"^обновила не ту",
        r"^обновил не ту",
    )
    return any(re.search(pattern, normalized) for pattern in correction_patterns)


def _looks_like_yes(text: str) -> bool:
    return text.strip().casefold() in {"да", "yes", "y", "ага", "исправь", "исправить", "да, исправь"}


def _looks_like_no(text: str) -> bool:
    return text.strip().casefold() in {"нет", "оставь", "не надо", "нет, оставь"}


def _feedback_prompt() -> str:
    return (
        "Поняла.\n\n"
        "Что должно было произойти?\n\n"
        "Например:\n"
        "- Это товар\n"
        "- Это задача\n"
        "- Не нужно было задавать уточнения\n"
        "- Неверно определена база\n"
        "- Неверно извлечена цена\n"
        "- Нужно было создать две записи\n\n"
        "Опишите правильный результат одним сообщением."
    )


def _feedback_no_context_prompt() -> str:
    return (
        "Я зафиксирую ошибку, но не смогла определить, к какой предыдущей записи она относится.\n"
        "Пришли описание ошибки и правильный вариант одним сообщением."
    )


def _format_issue_saved(issue: SystemIssueRecord) -> str:
    return (
        "Ошибка зафиксирована.\n"
        f"Тип: {issue.classification.issue_type}\n"
        f"Критичность: {issue.classification.severity}\n"
        f"Я поняла правильный результат так:\n{issue.classification.expected_result or 'Требуется уточнение'}\n\n"
        "Исправить запись сейчас?\n"
        "Да\n"
        "Нет"
    )


def _format_issue_needs_clarification(issue: SystemIssueRecord) -> str:
    question = issue.classification.clarification_question or "Как должно было быть правильно?"
    return f"Ошибка зафиксирована.\n{question}"


def _format_fix_completed(result: dict[str, Any]) -> str:
    if result.get("errors"):
        return "Ошибка зафиксирована, но исправить запись автоматически не удалось.\nПричина:\n" + "; ".join(result["errors"])
    created = []
    if result.get("tasks_created"):
        created.append(f"задачи: {len(result['tasks_created'])}")
    if result.get("studies_created"):
        created.append(f"исследования: {len(result['studies_created'])}")
    if result.get("goods_created"):
        created.append(f"товары: {len(result['goods_created'])}")
    summary = ", ".join(created) if created else "новых записей нет"
    return (
        "Исправление выполнено.\n"
        f"Создано/обновлено: {summary}\n"
        "Ошибка оставлена в System Issues для последующего анализа правил."
    )


def _classification_payload(classification: Classification) -> dict[str, Any]:
    return {
        "tasks": [item.__dict__ for item in classification.tasks],
        "studies": [item.__dict__ for item in classification.studies],
        "goods": [item.__dict__ for item in classification.goods],
        "notes": classification.notes,
    }


def _issue_payload(issue: SystemIssueRecord) -> dict[str, Any]:
    return {
        "classification": issue.classification.__dict__,
        "detection_method": issue.detection_method,
        "status": issue.status,
        "input_data": issue.input_data,
        "description": issue.description,
        "solution": issue.solution,
        "detected_date": issue.detected_date,
        "fingerprint": issue.fingerprint,
    }


def _format_issue_input(original: str, interaction: dict[str, Any], command: str, correction: str) -> str:
    return original or correction


def _format_issue_description(classification: Any, interaction: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Исходный ввод: {interaction.get('input_text') or 'Не найден'}",
            f"Фактический результат: {classification.actual_result or 'Требуется анализ'}",
            f"Обратная связь пользователя: {classification.expected_result or 'Требуется анализ'}",
            f"Ожидаемый результат: {classification.expected_result or 'Требуется анализ'}",
            f"Какие сущности определены: {json.dumps(interaction.get('classification'), ensure_ascii=False)}",
            f"Какие записи созданы: {json.dumps(interaction.get('created'), ensure_ascii=False)}",
            f"Какие вопросы заданы: {json.dumps(interaction.get('questions') or [], ensure_ascii=False)}",
        ]
    )


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _extract_telegram_message_id(result: Any) -> int | None:
    if not isinstance(result, dict):
        return None
    message = result.get("result") if isinstance(result.get("result"), dict) else result
    value = message.get("message_id") if isinstance(message, dict) else None
    return int(value) if isinstance(value, int) else None


def _safe_error(exc: Exception) -> str:
    return str(exc).splitlines()[0][:500]


def _edit_guidance_message() -> str:
    return (
        "Не поняла, что именно нужно поправить.\n\n"
        "Можно написать так:\n"
        "- Исправь срок на пятницу\n"
        "- Исправь проект на СЫРЬЕВОЙ ТРЕЙДИНГ\n"
        "- Исправь направление на Бизнес\n"
        "- Исправь длительность на 15 минут\n"
        "- Исправь название на Поздравить с днем рождения Марии"
    )


def _format_created_summary(classification: Classification, *, from_clarification: bool = False) -> str:
    lines: list[str] = []
    if from_clarification:
        lines.append("Зафиксировала после уточнения:")
    for item in classification.tasks:
        lines.extend(
            [
                f"Добавила задачу: {item.title}",
                f"Направление: {item.area or 'Не указано'}",
                f"Проект: {item.project or 'Не указано'}",
                f"Дата исполнения: {item.due_date or 'Не указана'}",
                f"Длительность работы: {item.effort_minutes} минут" if item.effort_minutes else "Длительность работы: Не указана",
            ]
        )
    for item in classification.studies:
        lines.extend(
            [
                f"Добавила на изучение: {item.question}",
                f"Направление: {item.area or 'Не указано'}",
                f"Проект: {item.project or 'Не указано'}",
                f"Дата исполнения: {item.due_date or 'Не указана'}",
                f"Тип исследования: {item.research_type}",
                f"Формат результата: {item.result_format}",
            ]
        )
    for item in classification.goods:
        lines.extend(
            [
                f"Создан товар: {item.title}",
                f"Статус: {item.status or 'Не куплено'}",
                f"Цена: {item.price}" if item.price is not None else "Цена: Не указана",
                f"Валюта: {item.currency or 'Не указана'}",
            ]
        )
    lines.append("Если что-то не так, напиши одним сообщением, что изменить.")
    return "\n".join(lines)


def _format_updated_summary(classification: Classification) -> str:
    lines = ["Обновила запись:"]
    for item in classification.tasks:
        lines.extend(
            [
                f"Задача: {item.title}",
                f"Направление: {item.area or 'Не указано'}",
                f"Проект: {item.project or 'Не указано'}",
                f"Дата исполнения: {item.due_date or 'Не указана'}",
                f"Длительность работы: {item.effort_minutes} минут" if item.effort_minutes else "Длительность работы: Не указана",
            ]
        )
    for item in classification.studies:
        lines.extend(
            [
                f"На изучение: {item.question}",
                f"Направление: {item.area or 'Не указано'}",
                f"Проект: {item.project or 'Не указано'}",
                f"Дата исполнения: {item.due_date or 'Не указана'}",
                f"Тип исследования: {item.research_type}",
                f"Формат результата: {item.result_format}",
            ]
        )
    for item in classification.goods:
        lines.extend(
            [
                f"Товар: {item.title}",
                f"Статус: {item.status or 'Не куплено'}",
                f"Цена: {item.price}" if item.price is not None else "Цена: Не указана",
                f"Валюта: {item.currency or 'Не указана'}",
            ]
        )
    return "\n".join(lines)


def _apply_clarification_fallbacks(classification: Classification) -> Classification:
    for item in classification.tasks:
        if not item.project:
            item.project = "Общее"
        if "project" in item.missing:
            item.missing = [value for value in item.missing if value != "project"]
        if not item.area:
            item.area = "Прочее"
        if "area" in item.missing:
            item.missing = [value for value in item.missing if value != "area"]
    for item in classification.studies:
        if not item.project:
            item.project = "Общее"
        if "project" in item.missing:
            item.missing = [value for value in item.missing if value != "project"]
        if not item.area:
            item.area = "Прочее"
        if "area" in item.missing:
            item.missing = [value for value in item.missing if value != "area"]
    for item in classification.goods:
        if "title" in item.missing and item.title:
            item.missing = [value for value in item.missing if value != "title"]
    return classification


def _needs_study_questions(item: StudyItem) -> bool:
    description = item.description.lower()
    scope_markers = ("какие", "что", "сравн", "риск", "стоим", "марж", "услов", "этап", "срок", "вопрос")
    return not any(marker in description for marker in scope_markers)


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


def _resolve_pending_without_ai(
    pending_item: dict[str, Any],
    answer: str,
    *,
    today: str,
    projects: list[dict[str, str]],
) -> Classification | None:
    payload = pending_item.get("payload", {})
    item_type = payload.get("type")
    raw_item = payload.get("item", {})
    if item_type not in {"task", "study", "goods"} or not raw_item:
        return None

    item = dict(raw_item)
    project_name = _extract_project_from_answer(answer, projects)
    if project_name:
        item["project"] = project_name

    area = _extract_area_from_answer(answer)
    if area:
        item["area"] = area

    due_date = _extract_due_date(answer, today)
    if due_date:
        item["due_date"] = due_date

    if item_type == "study" and "Какие именно вопросы должны войти в исследование?" in "\n".join(
        pending_item.get("questions", [])
    ):
        item["description"] = f"{item.get('description', '').strip()}\n\nУточнение пользователя: {answer.strip()}".strip()
    if item_type == "goods" and not str(item.get("title") or "").strip():
        item["title"] = answer.strip()

    missing = list(item.get("missing", []))
    if item.get("project"):
        missing = [value for value in missing if value != "project"]
    if item.get("area"):
        missing = [value for value in missing if value != "area"]
    if item.get("due_date"):
        missing = [value for value in missing if value != "due_date"]
    if item_type == "goods" and item.get("title"):
        missing = [value for value in missing if value != "title"]
    item["missing"] = missing

    if missing:
        return None

    item["confidence"] = max(float(item.get("confidence") or 0.0), 0.85)
    if item_type == "task":
        return Classification(tasks=[TaskItem(**item)], studies=[], notes=["resolved pending clarification"])
    if item_type == "study":
        return Classification(tasks=[], studies=[StudyItem(**item)], notes=["resolved pending clarification"])
    return Classification(tasks=[], studies=[], goods=[GoodsItem(**item)], notes=["resolved pending clarification"])


def _extract_project_from_answer(answer: str, projects: list[dict[str, str]]) -> str | None:
    answer_lower = answer.casefold()
    for project in projects:
        name = str(project.get("name") or "").strip()
        if name and name.casefold() in answer_lower:
            return name
    return None


def _extract_area_from_answer(answer: str) -> str | None:
    answer_lower = answer.casefold()
    for area in ("Работа", "Бизнес", "Личное развитие", "Семья", "Прочее"):
        if area.casefold() in answer_lower:
            return area
    if answer_lower.strip() == "личное":
        return "Личное развитие"
    normalized = _normalize_area(answer.strip())
    return normalized if normalized in {"Работа", "Бизнес", "Личное развитие", "Семья", "Прочее"} else None


def _looks_like_edit_request(text: str) -> bool:
    lower = text.strip().casefold()
    return lower.startswith(("поправь", "исправь", "измени", "не так", "неправильно"))


def _recent_payload(item_type: str, url: str, item: dict[str, Any]) -> dict[str, Any]:
    return {"type": item_type, "url": url, "page_id": _extract_notion_page_id(url), "item": item}


def _extract_notion_page_id(url: str) -> str:
    raw = url.rstrip("/").split("-")[-1].split("?")[0]
    if len(raw) == 32:
        return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
    return raw


def _apply_edit_to_recent(
    recent: dict[str, Any],
    text: str,
    *,
    today: str,
    projects: list[dict[str, str]],
) -> dict[str, Any] | None:
    item_type = recent.get("type")
    if item_type not in {"task", "study"}:
        return None
    updated = {
        "type": recent["type"],
        "url": recent["url"],
        "page_id": recent["page_id"],
        "item": dict(recent["item"]),
    }
    item = updated["item"]
    changed = False

    title = _extract_replacement_value(text, ("название", "задачу", "задача", "вопрос", "на изучение"))
    if title:
        key = "title" if item_type == "task" else "question"
        item[key] = title
        changed = True

    project_name = _extract_project_from_answer(text, projects)
    if project_name:
        item["project"] = project_name
        changed = True

    area = _extract_area_from_answer(text)
    if area:
        item["area"] = area
        changed = True

    due_date = _extract_due_date(text, today)
    if due_date:
        item["due_date"] = due_date
        changed = True

    effort = _extract_effort_from_answer(text)
    if effort is not None and item_type == "task":
        item["effort_minutes"] = effort
        changed = True

    if item_type == "study":
        research_type = _extract_research_type(text)
        if research_type:
            item["research_type"] = research_type
            item["result_format"] = "Подробная справка" if research_type == "Глубокое" else "Краткая справка"
            changed = True

    if item_type == "task" and _looks_like_birthday_correction(text):
        current_title = str(item.get("title") or "")
        current_title = current_title.replace("Напомнить", "Поздравить").replace("напомнить", "Поздравить")
        current_title = current_title.replace("Напомни", "Поздравить").replace("напомни", "Поздравить")
        current_title = current_title.replace("о дне рождения", "с днем рождения")
        item["title"] = current_title
        item["desired_result"] = "Совершенное поздравление"
        changed = True

    if not changed:
        return None
    return updated


def _extract_replacement_value(text: str, markers: tuple[str, ...]) -> str | None:
    lower = text.casefold()
    for marker in markers:
        for pattern in (f"{marker} на ", f"{marker}:"):
            index = lower.find(pattern)
            if index != -1:
                return text[index + len(pattern) :].strip(" .:\n\t")
    return None


def _extract_effort_from_answer(text: str) -> int | None:
    import re

    lower = text.casefold()
    match = re.search(r"(\d+)\s*(час|часа|часов)", lower)
    if match:
        return int(match.group(1)) * 60
    match = re.search(r"(\d+)\s*(минут|мин|м\b)", lower)
    if match:
        return int(match.group(1))
    return None


def _extract_research_type(text: str) -> str | None:
    lower = text.casefold()
    if "глубок" in lower or "подроб" in lower:
        return "Глубокое"
    if "прост" in lower or "кратк" in lower:
        return "Простое"
    return None


def _looks_like_birthday_correction(text: str) -> bool:
    lower = text.casefold()
    return "поздрав" in lower and "рожд" in lower
