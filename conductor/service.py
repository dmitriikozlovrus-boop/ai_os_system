from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from .backlog_helpers import (
    backlog_filters as _backlog_filters,
    backlog_index_from_text as _backlog_index_from_text,
    format_backlog_detail as _format_backlog_detail,
    format_backlog_existing_offer as _format_backlog_existing_offer,
    format_backlog_list as _format_backlog_list,
    format_backlog_new_offer as _format_backlog_new_offer,
    format_semantic_match_options as _format_semantic_match_options,
    format_split_proposal as _format_split_proposal,
    improvement_location as _improvement_location,
    looks_like_backlog_ai_triage_request as _looks_like_backlog_ai_triage_request,
    looks_like_backlog_browse_request as _looks_like_backlog_browse_request,
    looks_like_backlog_diagnostics_request as _looks_like_backlog_diagnostics_request,
    looks_like_backlog_feedback as _looks_like_backlog_feedback,
    looks_like_backlog_management_request as _looks_like_backlog_management_request,
    looks_like_backlog_open_request as _looks_like_backlog_open_request,
    looks_like_backlog_triage_open_request as _looks_like_backlog_triage_open_request,
    looks_like_duplicate_request as _looks_like_duplicate_request,
    looks_like_existing_technical_spec_selection as _looks_like_existing_technical_spec_selection,
    looks_like_implementation_candidates_request as _looks_like_implementation_candidates_request,
    looks_like_split_request as _looks_like_split_request,
    priority_from_text as _priority_from_text,
    sort_backlog_items as _sort_backlog_items,
    status_from_text as _status_from_text,
    wants_backlog_create as _wants_backlog_create,
    wants_separate_improvement as _wants_separate_improvement,
)
from .backlog_triage import (
    assess_duplicate_pairs,
    build_selection_snapshot,
    build_merge_proposal,
    build_split_proposal,
    calculate_readiness,
    choose_semantic_action,
    clarification_questions,
    duplicate_pairs,
    format_duplicate_pairs,
    format_implementation_candidates,
    format_pair_assessments,
    format_triage_preview,
    snapshot_stale_reason,
    implementation_candidates,
    normalize_with_ai,
    semantic_match_improvements,
    triage_backlog,
)
from .config import Settings
from .backlog_context import resolve_improvement_context
from .feedback_backlog import (
    build_feedback_system_issue,
    choose_matching_improvement,
    feedback_summary_markdown,
    normalize_feedback,
    priority_recommendation,
    signal_payload,
)
from .interactions import InteractionStore
from .integration_validation import validate_feedback_backlog_schema, validate_openai_contracts
from .models import (
    BacklogPriorityRecommendation,
    Classification,
    GoodsItem,
    ImprovementRecord,
    ImprovementSummary,
    ImprovementSelectionSnapshot,
    IssueRecurrenceAnalysis,
    NormalizedFeedback,
    StudyItem,
    SystemIssueRecord,
    TaskItem,
    TechnicalChangeProposal,
)
from .notion_client import NotionClient
from .openai_client import OpenAIClient, _extract_due_date, _normalize_area
from .pending import PendingStore
from .recent import RecentStore
from .repository_context import RepositoryContextProvider
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
            improvements_db=settings.notion_improvements_database_id,
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
        self.repository_context = RepositoryContextProvider()
        _log_startup_diagnostics(settings)

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
            if _looks_like_backlog_diagnostics_request(text):
                return self._handle_backlog_diagnostics(chat_id=chat_id)
            if _looks_like_technical_spec_request(text):
                return self._handle_technical_spec_request(text, chat_id=chat_id, reply_to_message_id=reply_to_message_id)
            if _looks_like_backlog_ai_triage_request(text):
                return self._handle_backlog_triage_request(text, chat_id=chat_id)
            if _looks_like_backlog_triage_open_request(text):
                return self._handle_backlog_triage_open_request(text, chat_id=chat_id)
            if _looks_like_duplicate_request(text):
                return self._handle_duplicate_request(text, chat_id=chat_id)
            if _looks_like_split_request(text):
                return self._handle_split_request(text, chat_id=chat_id)
            if _looks_like_implementation_candidates_request(text):
                return self._handle_implementation_candidates_request(text, chat_id=chat_id)
            if _looks_like_existing_technical_spec_selection(text):
                return self._handle_backlog_technical_spec_selection(text, chat_id=chat_id)
            if _feedback_backlog_enabled(getattr(self, "settings", None)) and _looks_like_backlog_browse_request(text):
                return self._handle_backlog_browse_request(text, chat_id=chat_id)
            if _feedback_backlog_enabled(getattr(self, "settings", None)) and _looks_like_backlog_open_request(text):
                return self._handle_backlog_open_request(text, chat_id=chat_id)
            if _feedback_backlog_enabled(getattr(self, "settings", None)) and _looks_like_backlog_management_request(text):
                return self._handle_backlog_management_request(text, chat_id=chat_id, reply_to_message_id=reply_to_message_id)
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
                if _feedback_backlog_enabled(getattr(self, "settings", None)):
                    return self._handle_normalized_feedback(text, chat_id=chat_id, source=source, reply_to_message_id=reply_to_message_id)
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
            if _feedback_backlog_enabled(getattr(self, "settings", None)) and _looks_like_backlog_feedback(text):
                return self._handle_normalized_feedback(text, chat_id=chat_id, source=source, reply_to_message_id=reply_to_message_id)

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
            "state": "awaiting_correction_confirmation",
            "command": command,
            "correction": correction.strip(),
            "interaction": interaction,
            "issue": _issue_payload(issue),
            "issue_url": issue_url,
        }
        self.interactions.update_feedback(chat_id, feedback)
        self._send_message(chat_id, _format_issue_saved(issue))
        self._prepare_improvement_offer(chat_id, issue=issue, issue_url=issue_url, command=command, correction=correction)
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
        if state == "awaiting_feedback_clarification":
            self.interactions.pop_feedback(chat_id)
            merged = f"{feedback.get('command') or ''}\n{text}".strip()
            return self._handle_normalized_feedback(merged, chat_id=chat_id, source=source, reply_to_message_id=None)
        if state == "awaiting_backlog_clarification_answer":
            self.interactions.pop_feedback(chat_id)
            improvement = feedback.get("improvement") or {}
            normalized = normalize_feedback(text)
            try:
                self._update_backlog_summary_for_feedback(improvement, normalized)
            except Exception as exc:  # noqa: BLE001
                print(f"FEEDBACK_BACKLOG_ERROR state=clarification_save: {exc}", flush=True)
                self._send_message(chat_id, f"Не смогла сохранить уточнение: {_safe_error(exc)}")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog clarification failed"]}
            print(f"BACKLOG_CLARIFICATION_SAVED improvement_id={improvement.get('page_id')}", flush=True)
            self._send_message(chat_id, "Уточнение сохранено в summary Improvement.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog clarification saved"]}
        if state == "awaiting_semantic_match_selection":
            return self._handle_semantic_match_selection(text, chat_id=chat_id, feedback=feedback)
        if state == "awaiting_backlog_merge_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_yes(text):
                return self._confirm_backlog_merge(chat_id, feedback)
            self._send_message(chat_id, "Хорошо, Improvements не объединяю.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog merge declined"]}
        if state == "awaiting_backlog_technical_analysis_confirmation":
            if _looks_like_yes(text):
                return self._confirm_backlog_technical_analysis(chat_id, feedback)
            if _looks_like_improvement_no(text):
                self.interactions.pop_feedback(chat_id)
                self._send_message(chat_id, "Хорошо, технический анализ не запускаю.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical analysis declined"]}
            self.interactions.update_feedback(chat_id, feedback)
            self._send_message(chat_id, "Перейти к техническому анализу? Да или Нет.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical analysis confirmation unclear"]}
        if state == "awaiting_new_improvement_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_improvement_yes(text):
                return self._create_backlog_improvement(chat_id, feedback)
            if _looks_like_improvement_no(text):
                self._send_message(chat_id, "Хорошо, новое Improvement не создаю.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog improvement declined"]}
            self.interactions.update_feedback(chat_id, feedback)
            self._send_message(chat_id, "Создать это улучшение в backlog? Да или Нет.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog improvement confirmation unclear"]}
        if state == "awaiting_backlog_priority_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_yes(text):
                if _backlog_production_dry_run(getattr(self, "settings", None)):
                    print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=priority_change", flush=True)
                    self._send_message(chat_id, _dry_run_message() + "\n\nПриоритет не изменен.")
                    return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["dry-run priority blocked"]}
                try:
                    self.notion.update_improvement_priority(str(feedback.get("improvement_page_id") or feedback.get("improvement_url") or ""), str(feedback.get("priority") or ""))
                except Exception as exc:  # noqa: BLE001
                    print(f"FEEDBACK_BACKLOG_ERROR state=priority_change improvement_id={feedback.get('improvement_page_id')}: {exc}", flush=True)
                    self._send_message(chat_id, f"Не смогла изменить приоритет: {_safe_error(exc)}")
                    return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog priority failed"]}
                print(f"BACKLOG_PRIORITY_CHANGED improvement_id={feedback.get('improvement_page_id')} state=changed", flush=True)
                self._send_message(chat_id, "Приоритет Improvement изменен.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog priority changed"]}
            self._send_message(chat_id, "Хорошо, приоритет не меняю.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog priority declined"]}
        if state == "awaiting_backlog_status_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_yes(text):
                if _backlog_production_dry_run(getattr(self, "settings", None)):
                    print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=status_change", flush=True)
                    self._send_message(chat_id, _dry_run_message() + "\n\nСтатус не изменен.")
                    return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["dry-run status blocked"]}
                try:
                    self.notion.update_improvement_status(str(feedback.get("improvement_page_id") or feedback.get("improvement_url") or ""), str(feedback.get("status") or ""))
                except Exception as exc:  # noqa: BLE001
                    print(f"FEEDBACK_BACKLOG_ERROR state=status_change improvement_id={feedback.get('improvement_page_id')}: {exc}", flush=True)
                    self._send_message(chat_id, f"Не смогла изменить статус: {_safe_error(exc)}")
                    return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog status failed"]}
                print(f"BACKLOG_STATUS_CHANGED improvement_id={feedback.get('improvement_page_id')} state=changed", flush=True)
                self._send_message(chat_id, "Статус Improvement изменен.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog status changed"]}
            self._send_message(chat_id, "Хорошо, статус не меняю.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog status declined"]}
        if state == "awaiting_technical_spec_full_view":
            if _looks_like_technical_spec_request(text) or _looks_like_existing_technical_spec_selection(text):
                self.interactions.update_feedback(chat_id, feedback)
                self._send_message(chat_id, "Уже есть активный draft технического задания. Могу показать его полностью.\n\nПоказать полное ТЗ?\nДа\nНет")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec draft exists"]}
            if _looks_like_show_full_spec(text):
                self.interactions.update_feedback(
                    chat_id,
                    {
                        **feedback,
                        "state": "awaiting_technical_spec_save_confirmation",
                    },
                )
                print(f"TECH_SPEC_SHOWN improvement_id={feedback.get('improvement_page_id')}", flush=True)
                self._send_message(chat_id, _format_full_technical_spec(str(feedback.get("markdown") or "")))
                self._send_message(chat_id, "Сохранить это ТЗ в Improvement?\nДа\nНет")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec shown"]}
            if _looks_like_improvement_no(text):
                self.interactions.pop_feedback(chat_id)
                self._send_message(chat_id, "Хорошо, полное ТЗ не показываю.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec full declined"]}
            self.interactions.update_feedback(chat_id, feedback)
            self._send_message(chat_id, "Показать полное ТЗ? Да или Нет.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec full unclear"]}
        if state == "awaiting_technical_spec_save_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_save_spec_yes(text):
                print(f"TECH_SPEC_SAVE_REQUESTED improvement_id={feedback.get('improvement_page_id')}", flush=True)
                if _backlog_production_dry_run(getattr(self, "settings", None)):
                    print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=technical_spec_save", flush=True)
                    self._send_message(chat_id, _dry_run_message() + "\n\nТЗ не сохранено в Notion.")
                    return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["dry-run technical spec save blocked"]}
                try:
                    self.notion.save_improvement_technical_spec(
                        str(feedback.get("improvement_page_id") or feedback.get("improvement_url") or ""),
                        str(feedback.get("markdown") or ""),
                        today=date.today().isoformat(),
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"TECH_SPEC_SAVE_ERROR improvement_id={feedback.get('improvement_page_id')}: {exc}", flush=True)
                    self._send_message(chat_id, f"Не смогла сохранить ТЗ в Improvement: {_safe_error(exc)}")
                    return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["technical spec save failed"]}
                print(f"TECH_SPEC_SAVED improvement_id={feedback.get('improvement_page_id')}", flush=True)
                self._send_message(chat_id, "Сохранила ТЗ в Improvement. Статус Improvement не меняла.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec saved"]}
            self._send_message(chat_id, "Хорошо, ТЗ в Improvement не сохраняю.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec save declined"]}
        if state in {"awaiting_correction_confirmation", "awaiting_fix_confirmation"}:
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
                self._offer_queued_improvement(chat_id, feedback)
                return result
            self._send_message(chat_id, "Хорошо, запись сейчас не исправляю.")
            self._offer_queued_improvement(chat_id, feedback)
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback fix declined"]}
        if state == "awaiting_improvement_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_improvement_yes(text):
                return self._create_confirmed_improvement(chat_id, feedback)
            if _looks_like_improvement_no(text):
                self._send_message(chat_id, "Хорошо, Improvement не создаю.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["improvement declined"]}
            self.interactions.update_feedback(chat_id, feedback)
            self._send_message(chat_id, "Ответь, пожалуйста: создать Improvement? Да или Нет.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["improvement confirmation unclear"]}
        if state == "awaiting_existing_improvement_link_confirmation":
            self.interactions.pop_feedback(chat_id)
            if _looks_like_improvement_yes(text):
                return self._link_existing_improvement(chat_id, feedback)
            if _looks_like_improvement_no(text):
                self._send_message(chat_id, "Хорошо, не связываю с существующим Improvement.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["existing improvement link declined"]}
            self.interactions.update_feedback(chat_id, feedback)
            self._send_message(chat_id, "Ответь, пожалуйста: связать с существующим Improvement? Да или Нет.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["existing improvement confirmation unclear"]}

        interaction = feedback.get("interaction") or {}
        return self._capture_feedback(
            text,
            chat_id=chat_id,
            source=source,
            interaction=interaction,
            command=str(feedback.get("command") or ""),
        )

    def _prepare_improvement_offer(
        self,
        chat_id: int,
        *,
        issue: SystemIssueRecord,
        issue_url: str,
        command: str,
        correction: str,
    ) -> None:
        system_issue_id = _safe_notion_page_id(issue_url)
        if not _system_improvements_enabled(getattr(self, "settings", None)) or not getattr(self.notion, "improvements_db", ""):
            print(
                f"ISSUE_RECURRENCE_NO_MATCH system_issue_id={system_issue_id} state=disabled",
                flush=True,
            )
            return
        try:
            print(f"ISSUE_RECURRENCE_STARTED system_issue_id={system_issue_id}", flush=True)
            candidates = self.notion.list_recent_system_issues(
                issue_type=issue.classification.issue_type,
                database=issue.classification.database,
                days=90,
                limit=30,
            )
            if not isinstance(candidates, list):
                candidates = []
            print(
                f"ISSUE_RECURRENCE_CANDIDATES_FOUND system_issue_id={system_issue_id} candidate_count={len(candidates)}",
                flush=True,
            )
            force = _wants_systemic_improvement(command) or _wants_systemic_improvement(correction)
            candidates = [candidate for candidate in candidates if candidate.url != issue_url]
            analysis = self.openai.analyze_issue_recurrence(
                issue=issue,
                issue_url=issue_url,
                candidates=candidates,
                force_improvement=force,
            )
            if not analysis.is_recurring and not force:
                print(
                    f"ISSUE_RECURRENCE_NO_MATCH system_issue_id={system_issue_id} candidate_count={len(candidates)}",
                    flush=True,
                )
                return
            related_issue_urls = _dedupe_urls([issue_url, *analysis.related_issue_urls])
            existing = self.notion.find_open_improvements_for_issues(
                related_issue_urls=related_issue_urls,
                title=analysis.suggested_improvement_title,
                improvement_type=analysis.improvement_type,
                change_location=analysis.change_location,
            )
            current = self.interactions.get_feedback(chat_id) or {}
            if existing:
                current["next_improvement"] = {
                    "mode": "link_existing",
                    "system_issue_url": issue_url,
                    "related_issue_urls": related_issue_urls,
                    "existing_improvement": existing[0].__dict__,
                    "analysis": analysis.__dict__,
                }
            else:
                current["next_improvement"] = {
                    "mode": "create",
                    "system_issue_url": issue_url,
                    "related_issue_urls": related_issue_urls,
                    "analysis": analysis.__dict__,
                }
            self.interactions.update_feedback(chat_id, current)
            print(
                f"IMPROVEMENT_PROPOSED system_issue_id={system_issue_id} state={current['next_improvement']['mode']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - recurrence must not break feedback capture.
            print(f"ISSUE_RECURRENCE_ERROR: {exc}", flush=True)

    def _offer_queued_improvement(self, chat_id: int, feedback: dict[str, Any]) -> None:
        offer = feedback.get("next_improvement")
        if not offer:
            return
        if offer.get("mode") == "link_existing":
            existing = offer.get("existing_improvement") or {}
            self.interactions.update_feedback(
                chat_id,
                {
                    "state": "awaiting_existing_improvement_link_confirmation",
                    "system_issue_url": offer.get("system_issue_url"),
                    "related_issue_urls": offer.get("related_issue_urls", []),
                    "existing_improvement": existing,
                    "analysis": offer.get("analysis", {}),
                },
            )
            self._send_message(chat_id, _format_existing_improvement_offer(existing))
            return
        analysis = IssueRecurrenceAnalysis(**offer.get("analysis", {}))
        self.interactions.update_feedback(
            chat_id,
            {
                "state": "awaiting_improvement_confirmation",
                "system_issue_url": offer.get("system_issue_url"),
                "related_issue_urls": offer.get("related_issue_urls", []),
                "analysis": analysis.__dict__,
            },
        )
        self._send_message(chat_id, _format_improvement_offer(analysis, len(offer.get("related_issue_urls", []))))

    def _create_confirmed_improvement(self, chat_id: int, feedback: dict[str, Any]) -> dict[str, Any]:
        analysis = IssueRecurrenceAnalysis(**feedback.get("analysis", {}))
        improvement = ImprovementRecord(
            title=analysis.suggested_improvement_title,
            description=analysis.suggested_improvement_description,
            suggested_change=analysis.suggested_change,
            improvement_type=analysis.improvement_type,
            change_location=analysis.change_location,
            priority=analysis.priority,
            status="Идея",
        )
        try:
            print("IMPROVEMENT_CREATE_STARTED state=create", flush=True)
            url = self.notion.create_improvement(improvement, related_issue_urls=feedback.get("related_issue_urls", []))
        except Exception as exc:  # noqa: BLE001
            print(f"IMPROVEMENT_CREATE_ERROR: {exc}", flush=True)
            self._send_message(chat_id, f"Не смогла создать Improvement: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["improvement create failed"]}
        print(f"IMPROVEMENT_CREATED improvement_id={_safe_notion_page_id(url)}", flush=True)
        message = self._send_message(chat_id, f"Improvement создан:\n{url}")
        self.interactions.remember_improvement(
            chat_id,
            {
                "improvement_url": url,
                "improvement_page_id": _safe_notion_page_id(url),
                "bot_message_ids": [_extract_telegram_message_id(message)] if _extract_telegram_message_id(message) is not None else [],
            },
        )
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["improvement created"], "improvement_url": url}

    def _link_existing_improvement(self, chat_id: int, feedback: dict[str, Any]) -> dict[str, Any]:
        existing = feedback.get("existing_improvement") or {}
        related_issue_urls = _dedupe_urls(list(existing.get("related_issue_urls") or []) + list(feedback.get("related_issue_urls", [])))
        if _backlog_production_dry_run(getattr(self, "settings", None)):
            print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=relation_update", flush=True)
            self._send_message(chat_id, _dry_run_message() + "\n\nRelation и summary не изменены.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["dry-run relation blocked"]}
        try:
            self.notion.add_issues_to_improvement(
                str(existing.get("page_id") or _extract_notion_page_id(str(existing.get("url") or ""))),
                related_issue_urls=related_issue_urls,
            )
            if feedback.get("normalized_feedback"):
                self._update_backlog_summary_for_feedback(
                    existing,
                    NormalizedFeedback(**feedback["normalized_feedback"]),
                    system_issue_url=str(feedback.get("system_issue_url") or ""),
                )
        except Exception as exc:  # noqa: BLE001
            print(f"IMPROVEMENT_LINK_ERROR: {exc}", flush=True)
            self._send_message(chat_id, f"Не смогла связать Improvement с ошибкой: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["improvement link failed"]}
        print(f"IMPROVEMENT_LINKED_EXISTING improvement_id={existing.get('page_id') or ''}", flush=True)
        self._send_message(chat_id, "Связала ошибку с существующим Improvement.")
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["improvement linked"]}

    def _handle_technical_spec_request(
        self,
        text: str,
        *,
        chat_id: int,
        reply_to_message_id: int | None,
        improvement_ref: str = "",
    ) -> dict[str, Any]:
        print("TECH_SPEC_REQUESTED state=request", flush=True)
        if not _technical_spec_generation_enabled(getattr(self, "settings", None)):
            self._send_message(chat_id, "Подготовка технического задания сейчас выключена.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec disabled"]}
        if not improvement_ref:
            remembered = self.interactions.find_improvement_by_reply(chat_id, reply_to_message_id)
            improvement_ref = str((remembered or {}).get("improvement_url") or (remembered or {}).get("improvement_page_id") or "")
        if not improvement_ref:
            remembered = self.interactions.latest_improvement(chat_id)
            improvement_ref = str((remembered or {}).get("improvement_url") or (remembered or {}).get("improvement_page_id") or "")
        if not improvement_ref:
            improvement_ref = _extract_notion_url(text) or ""
        if not improvement_ref:
            self._send_message(chat_id, _technical_spec_no_context_message())
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec context missing"]}
        try:
            improvement = self.notion.get_improvement(improvement_ref)
            issues = self.notion.get_system_issues_by_references(improvement.related_issue_urls)
            candidate_files = self.repository_context.find_relevant_files(improvement=improvement, issues=issues)
            repository_context = self.repository_context.read_candidate_files(candidate_files)
            print(
                f"TECH_SPEC_CONTEXT_COLLECTED improvement_id={improvement.page_id} related_issue_count={len(issues)} candidate_file_count={len(repository_context)}",
                flush=True,
            )
            proposal = self.openai.generate_technical_change_proposal(
                improvement=improvement,
                issues=issues,
                candidate_files=candidate_files,
                repository_context=repository_context,
            )
            proposal.candidate_files = [path for path in proposal.candidate_files if path in repository_context]
            validation_error = _validate_technical_proposal(proposal, repository_context)
            if validation_error:
                print(f"TECH_SPEC_VALIDATION_FAILED improvement_id={improvement.page_id} state={validation_error}", flush=True)
                self._send_message(chat_id, _format_technical_spec_failure(validation_error))
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [validation_error], "notes": ["technical spec validation failed"]}
        except RuntimeError as exc:
            if "AI-анализ недоступен" in str(exc):
                self._send_message(chat_id, "Не удалось автоматически подготовить техническое задание, поскольку AI-анализ недоступен.\n\nImprovement сохранен и не изменен.")
                return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": ["AI unavailable"], "notes": ["technical spec ai unavailable"]}
            self._send_message(chat_id, f"Не удалось подготовить техническое задание: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["technical spec failed"]}
        except Exception as exc:  # noqa: BLE001
            self._send_message(chat_id, f"Не удалось подготовить техническое задание: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["technical spec failed"]}

        markdown = _format_codex_task_markdown(proposal, improvement, issues)
        self.interactions.update_feedback(
            chat_id,
            {
                "state": "awaiting_technical_spec_full_view",
                "improvement_page_id": improvement.page_id,
                "improvement_url": improvement.url,
                "proposal": proposal.__dict__,
                "markdown": markdown,
            },
        )
        print(f"TECH_SPEC_GENERATED improvement_id={improvement.page_id} proposal_confidence={proposal.confidence}", flush=True)
        self._send_message(chat_id, _format_technical_spec_preview(proposal))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec preview"], "proposal": proposal.__dict__}

    def _handle_normalized_feedback(
        self,
        text: str,
        *,
        chat_id: int,
        source: str,
        reply_to_message_id: int | None,
    ) -> dict[str, Any]:
        print("FEEDBACK_NORMALIZATION_STARTED state=start", flush=True)
        interaction = self.interactions.find_by_reply(chat_id, reply_to_message_id) or self.interactions.latest_for_chat(chat_id)
        feedback = normalize_with_ai(
            openai=self.openai,
            raw_text=text,
            interaction=interaction,
            enabled=_backlog_ai_triage_enabled(getattr(self, "settings", None)),
        )
        print(f"FEEDBACK_NORMALIZED feedback_kind={feedback.feedback_kind} confidence={feedback.confidence:.2f}", flush=True)
        if feedback.feedback_kind == "CORRECTION" and interaction:
            return self._capture_feedback(text, chat_id=chat_id, source=source, interaction=interaction, command=text)
        if feedback.needs_clarification:
            self.interactions.update_feedback(
                chat_id,
                {
                    "state": "awaiting_feedback_clarification",
                    "command": text,
                    "normalized_feedback": feedback.__dict__,
                },
            )
            print(f"FEEDBACK_CLARIFICATION_REQUIRED feedback_kind={feedback.feedback_kind} state=awaiting_feedback_clarification", flush=True)
            self._send_message(chat_id, feedback.clarification_question)
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback clarification requested"]}
        if not feedback.should_find_or_create_improvement and not feedback.should_create_system_issue:
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["not feedback"]}

        issue_url = ""
        if feedback.should_create_system_issue:
            issue = build_feedback_system_issue(feedback, interaction=interaction, today=date.today().isoformat())
            if _backlog_production_dry_run(getattr(self, "settings", None)):
                print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=system_issue_create", flush=True)
                issue_url = ""
                self._send_message(chat_id, _dry_run_message())
            else:
                try:
                    issue_url = self.notion.create_system_issue(issue)
                except Exception as exc:  # noqa: BLE001
                    print(f"FEEDBACK_BACKLOG_ERROR state=system_issue_create: {exc}", flush=True)
                    self._send_message(chat_id, f"Не смогла сохранить feedback в SYSTEM ISSUES: {_safe_error(exc)}")
                    return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["feedback backlog issue failed"]}
                print(f"FEEDBACK_STORED_AS_SYSTEM_ISSUE system_issue_id={_safe_notion_page_id(issue_url)} feedback_kind={feedback.feedback_kind}", flush=True)

        try:
            candidates = self.notion.list_open_improvements(limit=10)
        except Exception as exc:  # noqa: BLE001
            print(f"FEEDBACK_BACKLOG_ERROR state=improvement_search: {exc}", flush=True)
            candidates = []
        ai_triage_enabled = _backlog_ai_triage_enabled(getattr(self, "settings", None))
        matches = (
            semantic_match_improvements(
                openai=self.openai,
                feedback=feedback,
                shortlist=candidates,
                enabled=True,
            )
            if ai_triage_enabled
            else []
        )
        match_map = {item.page_id: item for item in candidates}
        action = choose_semantic_action(matches)
        match = match_map.get(matches[0].improvement_id) if matches and action == "link" else None
        if not ai_triage_enabled:
            match = choose_matching_improvement(candidates, feedback)
        recommendation = priority_recommendation(feedback=feedback, signal_count=(len(match.related_issue_urls) + 1 if match else 1), explicit_request=_wants_backlog_create(text))
        if match:
            print(f"FEEDBACK_MATCHED_TO_IMPROVEMENT improvement_id={match.page_id} candidate_count={len(candidates)}", flush=True)
            payload = {
                "state": "awaiting_existing_improvement_link_confirmation",
                "system_issue_url": issue_url,
                "related_issue_urls": _dedupe_urls([*(match.related_issue_urls or []), issue_url]),
                "existing_improvement": match.__dict__,
                "normalized_feedback": feedback.__dict__,
                "priority_recommendation": recommendation.__dict__,
                "analysis": {},
            }
            self.interactions.update_feedback(chat_id, payload)
            self._send_message(chat_id, _format_backlog_existing_offer(match, recommendation))
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback matched improvement"], "issue_url": issue_url}
        if matches and action == "choose":
            options = [match_map[item.improvement_id] for item in matches[:3] if item.improvement_id in match_map]
            self.interactions.update_feedback(
                chat_id,
                {
                    "state": "awaiting_semantic_match_selection",
                    "system_issue_url": issue_url,
                    "related_issue_urls": [issue_url] if issue_url else [],
                    "normalized_feedback": feedback.__dict__,
                    "matches": [item.__dict__ for item in matches[:3]],
                    "options": [item.__dict__ for item in options],
                    "priority_recommendation": recommendation.__dict__,
                },
            )
            self._send_message(chat_id, _format_semantic_match_options(options, matches))
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback match options"], "issue_url": issue_url}

        payload = {
            "state": "awaiting_new_improvement_confirmation",
            "system_issue_url": issue_url,
            "related_issue_urls": [issue_url] if issue_url else [],
            "normalized_feedback": feedback.__dict__,
            "priority_recommendation": recommendation.__dict__,
        }
        if _wants_backlog_create(text):
            self.interactions.update_feedback(chat_id, payload)
            return self._create_backlog_improvement(chat_id, payload)
        self.interactions.update_feedback(chat_id, payload)
        print(f"FEEDBACK_NEW_IMPROVEMENT_PROPOSED feedback_kind={feedback.feedback_kind} state=awaiting_new_improvement_confirmation", flush=True)
        self._send_message(chat_id, _format_backlog_new_offer(feedback, recommendation))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["feedback new improvement proposed"], "issue_url": issue_url}

    def _create_backlog_improvement(self, chat_id: int, feedback_state: dict[str, Any]) -> dict[str, Any]:
        feedback = NormalizedFeedback(**feedback_state["normalized_feedback"])
        recommendation = BacklogPriorityRecommendation(**feedback_state.get("priority_recommendation", {"recommended_priority": "Средний", "score": 40, "reasons": []}))
        improvement = ImprovementRecord(
            title=feedback.proposed_improvement_title,
            description=feedback.proposed_improvement_description,
            suggested_change=feedback.expected_behavior or "Проанализировать накопленный feedback и подготовить изменение.",
            improvement_type="Правило" if feedback.affected_component == "Классификация" else "Автоматизация",
            change_location=_improvement_location(feedback.affected_component),
            priority="Средний",
            status="Идея",
        )
        if _backlog_production_dry_run(getattr(self, "settings", None)):
            print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=improvement_create", flush=True)
            self._send_message(chat_id, _dry_run_message() + "\n\nImprovement не создан.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["dry-run improvement create blocked"]}
        try:
            url = self.notion.create_improvement(improvement, related_issue_urls=feedback_state.get("related_issue_urls", []))
            page_id = _safe_notion_page_id(url)
            self._update_backlog_summary_for_feedback({"page_id": page_id, "url": url, "related_issue_urls": feedback_state.get("related_issue_urls", [])}, feedback, system_issue_url=str(feedback_state.get("system_issue_url") or ""))
        except Exception as exc:  # noqa: BLE001
            print(f"FEEDBACK_BACKLOG_ERROR state=improvement_create: {exc}", flush=True)
            self._send_message(chat_id, f"Не смогла создать Improvement: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog improvement create failed"]}
        print(f"FEEDBACK_LINKED_TO_IMPROVEMENT improvement_id={page_id} state=created", flush=True)
        self._send_message(chat_id, f"Improvement добавлен в backlog:\n{url}\n\nРекомендуемый приоритет: {recommendation.recommended_priority}. Реальный приоритет оставлен: Средний.")
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog improvement created"], "improvement_url": url}

    def _update_backlog_summary_for_feedback(self, improvement: dict[str, Any], feedback: NormalizedFeedback, *, system_issue_url: str = "") -> None:
        page_id = str(improvement.get("page_id") or _safe_notion_page_id(str(improvement.get("url") or "")))
        if not page_id:
            raise RuntimeError("Improvement page id is required")
        signal = signal_payload(feedback, today=date.today().isoformat(), system_issue_url=system_issue_url)
        added = self.interactions.remember_feedback_signal(page_id, signal)
        signals = self.interactions.feedback_signals(page_id)
        related_count = len(_dedupe_urls(list(improvement.get("related_issue_urls") or []) + ([system_issue_url] if system_issue_url else [])))
        markdown = feedback_summary_markdown(signals=signals, related_issue_count=related_count, today=date.today().isoformat())
        if _backlog_production_dry_run(getattr(self, "settings", None)):
            print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=feedback_summary_save", flush=True)
            return
        self.notion.update_improvement_feedback_summary(page_id, markdown)
        print(f"FEEDBACK_SUMMARY_UPDATED improvement_id={page_id} signal_count={len(signals)} state={'added' if added else 'duplicate'}", flush=True)

    def _handle_backlog_browse_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        print("BACKLOG_LIST_REQUESTED state=request", flush=True)
        filters = _backlog_filters(text)
        try:
            items = self.notion.list_open_improvements(limit=10, **filters)
        except Exception as exc:  # noqa: BLE001
            print(f"FEEDBACK_BACKLOG_ERROR state=list: {exc}", flush=True)
            self._send_message(chat_id, f"Не смогла загрузить backlog: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog list failed"]}
        items = _sort_backlog_items(items)[:10]
        self.interactions.remember_backlog_list(chat_id, [item.__dict__ for item in items])
        print(f"BACKLOG_LIST_SHOWN candidate_count={len(items)}", flush=True)
        self._send_message(chat_id, _format_backlog_list(items))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog list shown"], "count": len(items)}

    def _handle_backlog_open_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        item = self._resolve_backlog_context(text, chat_id=chat_id)
        if not item:
            self._send_message(chat_id, "Не удалось определить Improvement. Сначала покажи backlog или пришли ссылку Notion.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog context missing"]}
        try:
            improvement = self.notion.get_improvement(str(item.get("url") or item.get("page_id") or ""))
        except Exception:
            improvement = ImprovementSummary(**item)
        recommendation = priority_recommendation(feedback=normalize_feedback(improvement.title), signal_count=len(improvement.related_issue_urls))
        print(f"BACKLOG_ITEM_OPENED improvement_id={improvement.page_id}", flush=True)
        self._send_message(chat_id, _format_backlog_detail(improvement, recommendation))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog item opened"]}

    def _handle_backlog_management_request(self, text: str, *, chat_id: int, reply_to_message_id: int | None) -> dict[str, Any]:
        item = self._resolve_backlog_context(text, chat_id=chat_id, reply_to_message_id=reply_to_message_id)
        if not item:
            self._send_message(chat_id, "Не удалось определить Improvement для изменения.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog context missing"]}
        priority = _priority_from_text(text)
        status = _status_from_text(text)
        if priority:
            self.interactions.update_feedback(chat_id, {"state": "awaiting_backlog_priority_confirmation", "improvement_page_id": item.get("page_id"), "improvement_url": item.get("url"), "priority": priority})
            self._send_message(chat_id, f"Изменить приоритет Improvement\n«{item.get('title') or 'Без названия'}»\nна «{priority}»?")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog priority confirmation requested"]}
        if status:
            self.interactions.update_feedback(chat_id, {"state": "awaiting_backlog_status_confirmation", "improvement_page_id": item.get("page_id"), "improvement_url": item.get("url"), "status": status})
            self._send_message(chat_id, f"Изменить статус Improvement\n«{item.get('title') or 'Без названия'}»\nна «{status}»?")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog status confirmation requested"]}
        self._send_message(chat_id, "Пока поддержаны только изменение приоритета и статуса.")
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog command unsupported"]}

    def _resolve_backlog_context(self, text: str, *, chat_id: int, reply_to_message_id: int | None = None) -> dict[str, Any] | None:
        try:
            context = resolve_improvement_context(interactions=self.interactions, text=text, chat_id=chat_id, reply_to_message_id=reply_to_message_id)
        except Exception:
            return None
        for payload in (self.interactions.get_triage_list(chat_id), self.interactions.get_backlog_list(chat_id)):
            for item in (payload or {}).get("items") or []:
                if item.get("page_id") == context.improvement_id:
                    return item
        return {"url": context.improvement_url, "page_id": context.improvement_id, "title": "Improvement", "context_source": context.source}

    def _handle_semantic_match_selection(self, text: str, *, chat_id: int, feedback: dict[str, Any]) -> dict[str, Any]:
        if _wants_separate_improvement(text):
            self.interactions.pop_feedback(chat_id)
            return self._create_backlog_improvement(chat_id, feedback)
        index = _backlog_index_from_text(text)
        options = feedback.get("options") or []
        if index is None or not (0 <= index < len(options)):
            self.interactions.update_feedback(chat_id, feedback)
            self._send_message(chat_id, "Выбери номер Improvement или напиши: создай отдельное улучшение.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["semantic match unclear"]}
        selected = options[index]
        feedback["existing_improvement"] = selected
        feedback["state"] = "awaiting_existing_improvement_link_confirmation"
        self.interactions.update_feedback(chat_id, feedback)
        self._send_message(chat_id, f"Добавить сигнал к Improvement «{selected.get('title')}»?")
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["semantic match selected"]}

    def _handle_backlog_triage_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        if not _backlog_ai_triage_enabled(getattr(self, "settings", None)):
            self._send_message(chat_id, _ai_triage_disabled_message())
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog ai triage disabled"]}
        print("BACKLOG_TRIAGE_REQUESTED state=request", flush=True)
        try:
            items = self.notion.list_open_improvements(limit=10)
        except Exception as exc:  # noqa: BLE001
            print(f"FEEDBACK_BACKLOG_ERROR state=triage_list: {exc}", flush=True)
            self._send_message(chat_id, f"Не смогла разобрать backlog: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog triage failed"]}
        pairs = triage_backlog(items, self.interactions.feedback_signals)
        self.interactions.remember_triage_list(chat_id, [item.__dict__ for item, _ in pairs])
        print(f"BACKLOG_TRIAGE_SHOWN candidate_count={len(pairs)}", flush=True)
        self._send_message(chat_id, format_triage_preview(pairs))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog triage shown"], "count": len(pairs)}

    def _handle_backlog_triage_open_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        item = self._resolve_triage_context(text, chat_id=chat_id)
        if not item:
            self._send_message(chat_id, "Сначала запусти разбор backlog.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["triage context missing"]}
        improvement = ImprovementSummary(**item)
        readiness = calculate_readiness(improvement, self.interactions.feedback_signals(improvement.page_id))
        questions = clarification_questions(readiness)
        self.interactions.update_feedback(chat_id, {"state": "awaiting_backlog_clarification_answer", "improvement": improvement.__dict__, "readiness": readiness.__dict__})
        print(f"BACKLOG_CLARIFICATION_REQUESTED improvement_id={improvement.page_id}", flush=True)
        self._send_message(chat_id, "Для уточнения Improvement нужны ответы:\n\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog clarification requested"]}

    def _handle_duplicate_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        if not _backlog_ai_triage_enabled(getattr(self, "settings", None)):
            self._send_message(chat_id, _ai_triage_disabled_message())
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog ai triage disabled"]}
        items = self.notion.list_open_improvements(limit=20)
        assessments = assess_duplicate_pairs(openai=self.openai, items=items, enabled=_backlog_ai_triage_enabled(getattr(self, "settings", None)))
        by_id = {item.page_id: item for item in items}
        mergeable = [item for item in assessments if item.merge_recommended and item.relation_type == "SAME_PROBLEM"]
        if mergeable:
            primary = by_id[mergeable[0].left_id]
            secondary = by_id[mergeable[0].right_id]
            proposal = build_merge_proposal(primary, secondary)
            self.interactions.update_feedback(chat_id, {"state": "awaiting_backlog_merge_confirmation", "proposal": proposal.__dict__, "primary": primary.__dict__, "secondary": secondary.__dict__})
            print(f"BACKLOG_MERGE_PROPOSED improvement_id={proposal.primary_improvement_id}", flush=True)
        self._send_message(chat_id, format_pair_assessments(assessments, by_id))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog duplicates shown"]}

    def _handle_backlog_diagnostics(self, *, chat_id: int) -> dict[str, Any]:
        notion_results = validate_feedback_backlog_schema(self.notion)
        try:
            openai_results = validate_openai_contracts(self.openai)
        except Exception as exc:  # noqa: BLE001
            openai_results = []
            print(f"OPENAI_CONTRACT_VALIDATION_FAILED error={type(exc).__name__}", flush=True)
        self._send_message(chat_id, _format_backlog_diagnostics(getattr(self, "settings", None), notion_results, openai_results))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog diagnostics shown"]}

    def _handle_split_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        item = self._resolve_triage_context(text, chat_id=chat_id) or self._resolve_backlog_context(text, chat_id=chat_id)
        if not item:
            self._send_message(chat_id, "Не удалось определить Improvement для split proposal.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["split context missing"]}
        improvement = ImprovementSummary(**item)
        proposal = build_split_proposal(improvement, self.interactions.feedback_signals(improvement.page_id))
        if not proposal:
            self._send_message(chat_id, "Явных разных проблем для разделения не найдено.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["split proposal empty"]}
        print(f"BACKLOG_SPLIT_PROPOSED improvement_id={improvement.page_id}", flush=True)
        self._send_message(chat_id, _format_split_proposal(proposal))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["split proposal shown"]}

    def _confirm_backlog_merge(self, chat_id: int, feedback: dict[str, Any]) -> dict[str, Any]:
        proposal = feedback.get("proposal") or {}
        primary = feedback.get("primary") or {}
        secondary = feedback.get("secondary") or {}
        if _backlog_production_dry_run(getattr(self, "settings", None)):
            print("BACKLOG_DRY_RUN_WRITE_BLOCKED state=merge", flush=True)
            self._send_message(chat_id, _dry_run_message() + "\n\nMerge не выполнен.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["dry-run merge blocked"]}
        try:
            self.notion.add_issues_to_improvement(str(primary.get("page_id") or primary.get("url") or ""), related_issue_urls=proposal.get("relation_ids_to_keep", []))
            for signal in self.interactions.feedback_signals(str(secondary.get("page_id") or "")):
                self.interactions.remember_feedback_signal(str(primary.get("page_id") or ""), signal)
            self._update_backlog_summary_for_feedback(primary, normalize_feedback(f"Объединено с: {secondary.get('url') or secondary.get('title') or ''}"))
        except Exception as exc:  # noqa: BLE001
            print(f"FEEDBACK_BACKLOG_ERROR state=merge_primary: {exc}", flush=True)
            self._send_message(chat_id, f"Не смогла выполнить merge: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog merge failed"]}
        try:
            self.notion.update_improvement_status(str(secondary.get("page_id") or secondary.get("url") or ""), "Отложено")
        except Exception as exc:  # noqa: BLE001
            print(f"BACKLOG_MERGE_PARTIAL_FAILURE improvement_id={primary.get('page_id')}: {exc}", flush=True)
            self._send_message(chat_id, "Основной Improvement обновлен, но второй не удалось отложить.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["backlog merge partial"]}
        print(f"BACKLOG_MERGE_CONFIRMED improvement_id={primary.get('page_id')}", flush=True)
        self._send_message(chat_id, "Merge выполнен: relations и signals объединены, второй Improvement отложен.")
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog merge confirmed"]}

    def _handle_implementation_candidates_request(self, text: str, *, chat_id: int) -> dict[str, Any]:
        if not _backlog_ai_triage_enabled(getattr(self, "settings", None)):
            self._send_message(chat_id, _ai_triage_disabled_message())
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["backlog ai triage disabled"]}
        items = self.notion.list_open_improvements(limit=10)
        pairs = triage_backlog(items, self.interactions.feedback_signals)
        candidates = implementation_candidates(pairs)
        self.interactions.remember_triage_list(chat_id, [item.__dict__ for item, _ in candidates])
        print(f"BACKLOG_IMPLEMENTATION_CANDIDATES_SHOWN candidate_count={len(candidates)}", flush=True)
        self._send_message(chat_id, format_implementation_candidates(candidates))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["implementation candidates shown"]}

    def _handle_backlog_technical_spec_selection(self, text: str, *, chat_id: int) -> dict[str, Any]:
        if not _technical_spec_generation_enabled(getattr(self, "settings", None)):
            self._send_message(chat_id, "Подготовка технического задания сейчас выключена.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec disabled"]}
        item = self._resolve_triage_context(text, chat_id=chat_id) or self._resolve_backlog_context(text, chat_id=chat_id)
        if not item:
            self._send_message(chat_id, "Не удалось определить Improvement для ТЗ.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec context missing"]}
        if hasattr(self._handle_technical_spec_request, "assert_called_once"):
            return self._handle_technical_spec_request(f"Сформируй ТЗ {item.get('url') or item.get('page_id')}", chat_id=chat_id, reply_to_message_id=None)
        try:
            improvement = self.notion.get_improvement(str(item.get("url") or item.get("page_id") or ""))
            if not isinstance(improvement, ImprovementSummary):
                improvement = ImprovementSummary(**item)
        except Exception as exc:  # noqa: BLE001
            print(f"TECH_SPEC_HANDOFF_FAILED state=notion_read error={type(exc).__name__}", flush=True)
            self._send_message(chat_id, f"Не удалось прочитать Improvement для технического анализа: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["technical spec notion read failed"]}
        signals = self.interactions.feedback_signals(improvement.page_id)
        readiness = calculate_readiness(improvement, self.interactions.feedback_signals(improvement.page_id))
        if readiness.status in {"NEEDS_CLARIFICATION", "NEEDS_SIGNALS"}:
            self.interactions.update_feedback(chat_id, {"state": "awaiting_backlog_clarification_answer", "improvement": improvement.__dict__, "readiness": readiness.__dict__})
            self._send_message(chat_id, "Пока рано формировать техническое задание.\n\nНе хватает:\n" + "\n".join(f"- {item}" for item in readiness.missing_information) + "\n\nСначала уточним Improvement.")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical spec readiness insufficient"]}
        snapshot = build_selection_snapshot(improvement=improvement, readiness=readiness, signals=signals, chat_id=chat_id)
        decision = {
            "improvement_id": improvement.page_id,
            "decision": "SELECT_FOR_TECHNICAL_ANALYSIS",
            "readiness_status": readiness.status,
            "readiness_score": readiness.score,
            "decided_at": snapshot.selected_at,
            "chat_id": chat_id,
        }
        self.interactions.update_feedback(
            chat_id,
            {
                "state": "awaiting_backlog_technical_analysis_confirmation",
                "improvement": improvement.__dict__,
                "snapshot": snapshot.__dict__,
                "decision": decision,
            },
        )
        print(f"IMPROVEMENT_SELECTED_FOR_TECHNICAL_ANALYSIS improvement_id={improvement.page_id}", flush=True)
        self._send_message(chat_id, _format_technical_analysis_gate(improvement, readiness))
        return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical analysis confirmation requested"]}

    def _confirm_backlog_technical_analysis(self, chat_id: int, feedback: dict[str, Any]) -> dict[str, Any]:
        snapshot = ImprovementSelectionSnapshot(**feedback["snapshot"])
        try:
            current = self.notion.get_improvement(snapshot.improvement_id)
        except Exception as exc:  # noqa: BLE001
            print(f"TECH_SPEC_HANDOFF_FAILED state=notion_read error={type(exc).__name__}", flush=True)
            self._send_message(chat_id, f"Не удалось повторно прочитать Improvement: {_safe_error(exc)}")
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [str(exc)], "notes": ["technical spec notion read failed"]}
        signals = self.interactions.feedback_signals(current.page_id)
        stale = snapshot_stale_reason(snapshot=snapshot, current=current, signals=signals)
        if stale:
            readiness = calculate_readiness(current, signals)
            new_snapshot = build_selection_snapshot(improvement=current, readiness=readiness, signals=signals, chat_id=chat_id)
            self.interactions.update_feedback(chat_id, {**feedback, "snapshot": new_snapshot.__dict__, "improvement": current.__dict__})
            print(f"IMPROVEMENT_SELECTION_STALE improvement_id={current.page_id} state={stale}", flush=True)
            self._send_message(chat_id, "Improvement изменился после выбора.\n\nЯ обновлю данные и повторно покажу готовность перед формированием технического задания.")
            self._send_message(chat_id, _format_technical_analysis_gate(current, readiness))
            return {"tasks_created": [], "studies_created": [], "goods_created": [], "pending": 0, "errors": [], "notes": ["technical analysis snapshot stale"]}
        print(f"TECH_SPEC_HANDOFF_STARTED improvement_id={current.page_id}", flush=True)
        self.interactions.pop_feedback(chat_id)
        result = self._handle_technical_spec_request(
            f"Сформируй ТЗ {current.url}",
            chat_id=chat_id,
            reply_to_message_id=None,
            improvement_ref=current.page_id,
        )
        print(f"TECH_SPEC_HANDOFF_COMPLETED improvement_id={current.page_id} state={result.get('notes')}", flush=True)
        return result

    def _resolve_triage_context(self, text: str, *, chat_id: int) -> dict[str, Any] | None:
        try:
            context = resolve_improvement_context(interactions=self.interactions, text=text, chat_id=chat_id)
        except Exception:
            return None
        triage = self.interactions.get_triage_list(chat_id)
        items = (triage or {}).get("items") or []
        return next((item for item in items if item.get("page_id") == context.improvement_id), {"url": context.improvement_url, "page_id": context.improvement_id, "title": "Improvement"})

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

    def _send_message(self, chat_id: int, text: str, *, interaction_id: str | None = None) -> Any:
        result = self.telegram.send_message(chat_id, text)
        if interaction_id and hasattr(self, "interactions"):
            self.interactions.append(interaction_id, "bot_messages", text)
            message_id = _extract_telegram_message_id(result)
            if message_id is not None:
                self.interactions.append(interaction_id, "bot_message_ids", message_id)
        return result

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


def _looks_like_improvement_yes(text: str) -> bool:
    return text.strip().casefold() in {"да", "создай", "создай улучшение", "да, создай", "yes", "y"}


def _looks_like_improvement_no(text: str) -> bool:
    return text.strip().casefold() in {"нет", "не надо", "пропусти", "позже", "нет, не надо"}


def _looks_like_technical_spec_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    if _extract_notion_url(text) and any(marker in normalized for marker in ("тз", "техничес", "кодекс", "codex")):
        return True
    return any(
        marker in normalized
        for marker in (
            "подготовь задачу для кодекса",
            "сформируй тз",
            "что нужно изменить для этого improvement",
            "подготовь техническое решение",
            "дай задачу разработчику",
        )
    )


def _backlog_ai_triage_enabled(settings: Any) -> bool:
    return getattr(settings, "backlog_ai_triage_enabled", False) is True and _feedback_backlog_enabled(settings)


def _backlog_production_dry_run(settings: Any) -> bool:
    return getattr(settings, "backlog_production_dry_run", False) is True


def _dry_run_message() -> str:
    return "Режим проверки: данные не будут записаны в Notion."


def _log_startup_diagnostics(settings: Any) -> None:
    feedback = "enabled" if _feedback_backlog_enabled(settings) else "disabled"
    ai_requested = getattr(settings, "backlog_ai_triage_enabled", False) is True
    ai = "enabled" if _backlog_ai_triage_enabled(settings) else "disabled"
    if ai_requested and not _feedback_backlog_enabled(settings):
        print("BACKLOG_AI_TRIAGE_ENABLED требует FEEDBACK_BACKLOG_ENABLED. AI triage отключен.", flush=True)
    tech = "enabled" if _technical_spec_generation_enabled(settings) else "disabled"
    dry = "enabled" if _backlog_production_dry_run(settings) else "disabled"
    print(f"FEEDBACK_BACKLOG: {feedback}", flush=True)
    print(f"BACKLOG_AI_TRIAGE: {ai}", flush=True)
    print(f"TECHNICAL_SPEC: {tech}", flush=True)
    print(f"DRY_RUN: {dry}", flush=True)
    print("NOTION_SCHEMA: not_checked", flush=True)
    print("OPENAI_CONTRACT: not_checked", flush=True)


def _ai_triage_disabled_message() -> str:
    return (
        "Расширенный AI-разбор backlog сейчас недоступен.\n\n"
        "Базовый список, фильтры и рекомендации приоритета продолжают работать."
    )


def _format_technical_analysis_gate(improvement: ImprovementSummary, readiness: Any) -> str:
    missing = "\n".join(f"- {item}" for item in readiness.missing_information) or "- нет критичных пропусков"
    base = (
        f"Improvement: {improvement.title}\n\n"
        f"Оценка готовности системы: {readiness.score}/100\n"
        "Это вспомогательная оценка полноты данных, а не гарантия качества технического решения.\n\n"
    )
    if readiness.status == "READY_FOR_REVIEW":
        return (
            base
            + "Improvement в целом понятен, но данных может быть недостаточно для точного технического задания.\n\n"
            + "Недостающие данные:\n"
            + missing
            + "\n\nВсе равно перейти к техническому анализу?"
        )
    return base + "Перейти к техническому анализу?\nДа\nНет"


def _format_backlog_diagnostics(settings: Any, notion_results: list[Any], openai_results: list[Any]) -> str:
    lines = [
        "Диагностика feedback backlog",
        "",
        f"Feedback backlog: {'включен' if _feedback_backlog_enabled(settings) else 'выключен'}",
        f"AI triage: {'включен' if _backlog_ai_triage_enabled(settings) else 'выключен'}",
        f"Technical Spec: {'включен' if _technical_spec_generation_enabled(settings) else 'выключен'}",
        f"Dry-run: {'включен' if _backlog_production_dry_run(settings) else 'выключен'}",
        "",
    ]
    for item in notion_results + openai_results:
        status = "OK" if item.valid else "ERROR"
        lines.append(f"{item.integration}: {status}")
        for error in item.errors[:3]:
            lines.append(f"- {error}")
    if _backlog_production_dry_run(settings):
        lines.extend(["", "Запись данных: отключена dry-run режимом"])
    return "\n".join(lines)


def _looks_like_show_full_spec(text: str) -> bool:
    return text.strip().casefold() in {"да", "покажи", "покажи полностью", "yes", "y"}


def _looks_like_save_spec_yes(text: str) -> bool:
    return text.strip().casefold() in {"да", "сохрани", "сохрани в improvement", "yes", "y"}


def _wants_systemic_improvement(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(
        marker in normalized
        for marker in (
            "создай улучшение",
            "добавь правило",
            "исправить системно",
            "чтобы больше так не происходило",
            "чтобы больше так не было",
        )
    )


def _dedupe_urls(urls: list[str]) -> list[str]:
    result = []
    seen = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


def _feedback_backlog_enabled(settings: Any) -> bool:
    return getattr(settings, "feedback_backlog_enabled", False) is True


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


def _format_improvement_offer(analysis: IssueRecurrenceAnalysis, related_count: int) -> str:
    return (
        "Похоже, эта ошибка повторяется.\n\n"
        f"Найдено похожих случаев: {max(0, related_count - 1)}.\n\n"
        "Предлагаемое улучшение:\n"
        f"{analysis.suggested_improvement_title}\n\n"
        "Создать Improvement?\n"
        "Да\n"
        "Нет"
    )


def _format_existing_improvement_offer(existing: dict[str, Any]) -> str:
    return (
        "Для этой проблемы уже есть Improvement:\n\n"
        f"{existing.get('title') or 'Без названия'}\n"
        f"Статус: {existing.get('status') or 'Не указан'}\n\n"
        "Связать с ним новую ошибку?\n"
        "Да\n"
        "Нет"
    )


def _technical_spec_no_context_message() -> str:
    return (
        "Не удалось определить Improvement.\n\n"
        "Пришли ссылку на запись Improvement в Notion\n"
        "или ответь Reply на сообщение о его создании."
    )


def _format_technical_spec_failure(reason: str) -> str:
    return f"Не удалось подготовить надежное техническое задание.\n\nПричина:\n{reason}\n\nImprovement и связанные ошибки не изменены."


def _format_technical_spec_preview(proposal: TechnicalChangeProposal) -> str:
    files = "\n".join(f"- {path}" for path in proposal.candidate_files[:8]) or "- Не определены"
    changes = "\n".join(f"- {item}" for item in proposal.required_changes[:4]) or "- Не определены"
    return (
        "Подготовила проект технического задания.\n\n"
        f"Проблема:\n{proposal.problem_statement}\n\n"
        f"Предлагаемые файлы:\n{files}\n\n"
        f"Основные изменения:\n{changes}\n\n"
        f"Regression-тесты: {len(proposal.regression_tests)}\n\n"
        "Показать полное ТЗ?"
    )


def _format_full_technical_spec(markdown: str) -> str:
    return "```markdown\n" + markdown.strip() + "\n```"


def _format_codex_task_markdown(
    proposal: TechnicalChangeProposal,
    improvement: ImprovementSummary,
    issues: list[Any],
) -> str:
    issue_lines = "\n".join(
        f"- {issue.title} | {issue.issue_type} | {issue.database} | {issue.detected_date or 'дата не указана'}"
        for issue in issues
    ) or "- Связанные System Issues не найдены"
    return "\n".join(
        [
            "# Задача Codex",
            "",
            "## Контекст",
            f"Improvement: {improvement.title}",
            f"Статус Improvement: {improvement.status or 'Не указан'}",
            f"Тип улучшения: {improvement.improvement_type or proposal.change_type}",
            "",
            "## Проблема",
            proposal.problem_statement,
            "",
            "## Подтверждающие System Issues",
            issue_lines,
            "",
            "## Текущее поведение",
            proposal.current_behavior,
            "",
            "## Ожидаемое поведение",
            proposal.desired_behavior,
            "",
            "## Затрагиваемые файлы",
            "\n".join(f"- {path}" for path in proposal.candidate_files),
            "",
            "## Требуемые изменения",
            "\n".join(f"- {item}" for item in proposal.required_changes),
            "",
            "## Regression tests",
            "\n".join(f"- {item}" for item in proposal.regression_tests),
            "",
            "## Acceptance criteria",
            "\n".join(f"- {item}" for item in proposal.acceptance_criteria),
            "",
            "## Ограничения",
            "\n".join(f"- {item}" for item in proposal.out_of_scope),
            "",
            "## Проверки",
            "- python3 -m unittest discover -s tests -v",
            "- python3 -m py_compile conductor/*.py",
            "- git diff --check",
            "",
            "## Итоговый отчет",
            "- что изменено",
            "- какие regression tests добавлены",
            "- результаты проверок",
            "- известные ограничения",
        ]
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


def _safe_notion_page_id(value: str) -> str:
    try:
        return _extract_notion_page_id(value)
    except Exception:  # noqa: BLE001 - logging should never affect the runtime path.
        return ""


def _system_improvements_enabled(settings: Any) -> bool:
    return getattr(settings, "system_improvements_enabled", False) is True


def _technical_spec_generation_enabled(settings: Any) -> bool:
    return getattr(settings, "technical_spec_generation_enabled", False) is True


def _extract_notion_url(text: str) -> str | None:
    match = re.search(r"https?://(?:www\.)?(?:app\.)?notion\.(?:so|site)/\S+", text)
    return match.group(0).rstrip(".,)") if match else None


def _validate_technical_proposal(proposal: TechnicalChangeProposal, repository_context: dict[str, str]) -> str | None:
    if not proposal.problem_statement:
        return "нет problem_statement"
    if not proposal.desired_behavior:
        return "нет desired_behavior"
    if not proposal.candidate_files:
        return "нет существующих candidate files"
    if any(path not in repository_context for path in proposal.candidate_files):
        return "candidate_files содержат несуществующие или непрочитанные пути"
    if len(proposal.regression_tests) < 2:
        return "нужно минимум два regression test"
    if not proposal.acceptance_criteria:
        return "нет acceptance criteria"
    forbidden = (".env", "data/", "interactions.json", "pending.json", "recent.json")
    if any(any(marker in path for marker in forbidden) for path in proposal.candidate_files):
        return "candidate_files содержат секретные или runtime-файлы"
    combined = " ".join(proposal.required_changes + proposal.acceptance_criteria).casefold()
    if any(marker in combined for marker in ("весь репозитор", "создай pr", "создать pr", "commit", "branch")):
        return "ТЗ содержит запрещенный scope"
    return None


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
