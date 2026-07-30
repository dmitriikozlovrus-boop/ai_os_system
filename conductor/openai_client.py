from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from .http import HttpError, request_json, request_multipart
from .models import (
    AREAS,
    CORRECTION_INTENTS,
    CORRECTION_TARGET_TYPES,
    GOODS_CURRENCIES,
    GOODS_STATUSES,
    GOODS_TYPES,
    GOODS_USAGE_PLACES,
    GOODS_USERS,
    IMPROVEMENT_CHANGE_LOCATIONS,
    IMPROVEMENT_PRIORITIES,
    IMPROVEMENT_TYPES,
    PROJECT_PRIORITIES,
    SYSTEM_ISSUE_DATABASES,
    SYSTEM_ISSUE_SEVERITIES,
    SYSTEM_ISSUE_TYPES,
    Classification,
    FeedbackEnrichment,
    ImprovementPairAssessment,
    IssueRecurrenceAnalysis,
    ImprovementSummary,
    ImprovementMatchCandidate,
    SystemIssueRecord,
    SystemIssueSummary,
    TechnicalChangeProposal,
    classification_from_dict,
    feedback_enrichment_from_dict,
    improvement_match_candidate_from_dict,
    improvement_pair_assessment_from_dict,
    issue_recurrence_analysis_from_dict,
    system_issue_classification_from_dict,
    technical_change_proposal_from_dict,
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


SYSTEM_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "issue_type": {"type": "string", "enum": sorted(SYSTEM_ISSUE_TYPES)},
        "severity": {"type": "string", "enum": sorted(SYSTEM_ISSUE_SEVERITIES)},
        "database": {"type": "string", "enum": sorted(SYSTEM_ISSUE_DATABASES)},
        "actual_result": {"type": "string"},
        "expected_result": {"type": "string"},
        "probable_cause": {"type": "string"},
        "title": {"type": "string"},
        "correction_intent": {"type": "string", "enum": sorted(CORRECTION_INTENTS)},
        "correction_target_type": {"type": "string", "enum": sorted(CORRECTION_TARGET_TYPES)},
        "corrected_fields": {"type": "array", "items": {"type": "string"}},
        "should_delete_original": {"type": "boolean"},
        "needs_user_clarification": {"type": "boolean"},
        "clarification_question": {"type": "string"},
    },
    "required": [
        "issue_type",
        "severity",
        "database",
        "actual_result",
        "expected_result",
        "probable_cause",
        "title",
        "correction_intent",
        "correction_target_type",
        "corrected_fields",
        "should_delete_original",
        "needs_user_clarification",
        "clarification_question",
    ],
}


ISSUE_RECURRENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_recurring": {"type": "boolean"},
        "related_issue_urls": {"type": "array", "items": {"type": "string"}},
        "recurrence_group_title": {"type": "string"},
        "similarity_reason": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "suggested_improvement_title": {"type": "string"},
        "suggested_improvement_description": {"type": "string"},
        "suggested_change": {"type": "string"},
        "improvement_type": {"type": "string", "enum": sorted(IMPROVEMENT_TYPES)},
        "change_location": {"type": "string", "enum": sorted(IMPROVEMENT_CHANGE_LOCATIONS)},
        "priority": {"type": "string", "enum": sorted(IMPROVEMENT_PRIORITIES)},
    },
    "required": [
        "is_recurring",
        "related_issue_urls",
        "recurrence_group_title",
        "similarity_reason",
        "confidence",
        "suggested_improvement_title",
        "suggested_improvement_description",
        "suggested_change",
        "improvement_type",
        "change_location",
        "priority",
    ],
}


TECHNICAL_CHANGE_PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "improvement_title": {"type": "string"},
        "problem_statement": {"type": "string"},
        "evidence_summary": {"type": "string"},
        "desired_behavior": {"type": "string"},
        "current_behavior": {"type": "string"},
        "likely_root_cause": {"type": "string"},
        "change_type": {"type": "string"},
        "affected_components": {"type": "array", "items": {"type": "string"}},
        "candidate_files": {"type": "array", "items": {"type": "string"}},
        "required_changes": {"type": "array", "items": {"type": "string"}},
        "regression_tests": {"type": "array", "items": {"type": "string"}},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "out_of_scope": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "improvement_title",
        "problem_statement",
        "evidence_summary",
        "desired_behavior",
        "current_behavior",
        "likely_root_cause",
        "change_type",
        "affected_components",
        "candidate_files",
        "required_changes",
        "regression_tests",
        "acceptance_criteria",
        "out_of_scope",
        "risks",
        "open_questions",
        "confidence",
    ],
}


FEEDBACK_ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "feedback_kind": {"type": "string", "enum": ["CONCRETE_ERROR", "GENERAL_PROBLEM", "IMPROVEMENT_IDEA", "CORRECTION", "NOT_FEEDBACK", "UNKNOWN"]},
        "normalized_title": {"type": "string"},
        "normalized_description": {"type": "string"},
        "actual_behavior": {"type": "string"},
        "expected_behavior": {"type": "string"},
        "affected_entity_type": {"type": "string"},
        "affected_database": {"type": "string", "enum": sorted(SYSTEM_ISSUE_DATABASES)},
        "affected_component": {"type": "string"},
        "severity": {"type": "string", "enum": sorted(SYSTEM_ISSUE_SEVERITIES)},
        "is_recurring_statement": {"type": "boolean"},
        "should_create_system_issue": {"type": "boolean"},
        "should_find_or_create_improvement": {"type": "boolean"},
        "proposed_improvement_title": {"type": "string"},
        "proposed_improvement_description": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "inferred_fields": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": "string"},
    },
    "required": [
        "feedback_kind",
        "normalized_title",
        "normalized_description",
        "actual_behavior",
        "expected_behavior",
        "affected_entity_type",
        "affected_database",
        "affected_component",
        "severity",
        "is_recurring_statement",
        "should_create_system_issue",
        "should_find_or_create_improvement",
        "proposed_improvement_title",
        "proposed_improvement_description",
        "confidence",
        "inferred_fields",
        "evidence",
        "needs_clarification",
        "clarification_question",
    ],
}


IMPROVEMENT_MATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "improvement_id": {"type": "string"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "relation_type": {"type": "string", "enum": ["SAME_PROBLEM", "RELATED_PROBLEM", "POSSIBLE_MATCH", "NOT_RELATED"]},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "contradictions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["improvement_id", "score", "relation_type", "reasons", "contradictions"],
            },
        }
    },
    "required": ["candidates"],
}


IMPROVEMENT_PAIR_ASSESSMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pairs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "left_id": {"type": "string"},
                    "right_id": {"type": "string"},
                    "relation_type": {"type": "string", "enum": ["SAME_PROBLEM", "OVERLAPPING", "RELATED_BUT_DISTINCT", "NOT_RELATED"]},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "shared_problem": {"type": "string"},
                    "differences": {"type": "array", "items": {"type": "string"}},
                    "merge_recommended": {"type": "boolean"},
                },
                "required": ["left_id", "right_id", "relation_type", "score", "shared_problem", "differences", "merge_recommended"],
            },
        }
    },
    "required": ["pairs"],
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

    def classify_system_issue(
        self,
        *,
        original_text: str,
        actual_context: dict[str, Any],
        command: str,
        correction: str,
    ):
        if not self.api_key:
            return _fallback_system_issue_classification(original_text, actual_context, correction)
        system = (
            "Ты классификатор системных ошибок сервиса 'Дирижер'. "
            "Верни только тип ошибки, критичность, базу, фактический результат, ожидаемый результат, причину и короткий title. "
            "Также определи intent исправления: CHANGE_ENTITY_TYPE, CHANGE_FIELDS, DELETE_OR_CANCEL, "
            "CREATE_MISSING_RECORD, UPDATE_WRONG_RECORD, NO_ACTION_EXPECTED или UNKNOWN. "
            "Не используй классификацию Task/Study/Goods."
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "original_text": original_text,
                            "actual_context": actual_context,
                            "feedback_command": command,
                            "user_correction": correction,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conductor_system_issue",
                    "schema": SYSTEM_ISSUE_SCHEMA,
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
            return system_issue_classification_from_dict(json.loads(_extract_response_text(data)))
        except Exception:
            return _fallback_system_issue_classification(original_text, actual_context, correction)

    def analyze_issue_recurrence(
        self,
        *,
        issue: SystemIssueRecord,
        issue_url: str,
        candidates: list[SystemIssueSummary],
        force_improvement: bool = False,
    ) -> IssueRecurrenceAnalysis:
        if not self.api_key:
            return _fallback_issue_recurrence(issue, issue_url, candidates, force_improvement=force_improvement)
        system = (
            "Ты анализируешь повторяемость системных ошибок сервиса 'Дирижер'. "
            "Сравни новую ошибку с кандидатами. Не считай ошибки связанными только из-за одинакового типа или базы. "
            "Связанность должна опираться на одинаковое направление исправления, похожую фактическую ошибку или одинаковый сбой маршрутизации/полей. "
            "Если найдено достаточно повторов, предложи одно Improvement, но не создавай его."
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "new_issue": _issue_for_recurrence(issue, issue_url),
                            "candidates": [_candidate_for_recurrence(candidate) for candidate in candidates],
                            "force_improvement": force_improvement,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conductor_issue_recurrence",
                    "schema": ISSUE_RECURRENCE_SCHEMA,
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
            analysis = issue_recurrence_analysis_from_dict(json.loads(_extract_response_text(data)))
            previous_related = [url for url in analysis.related_issue_urls if url != issue_url]
            recurring = len(previous_related) >= 2 or (len(previous_related) >= 1 and issue.classification.severity == "Высокая")
            if force_improvement and (previous_related or candidates):
                recurring = True
            if not recurring:
                analysis.is_recurring = False
            return analysis
        except Exception:
            return _fallback_issue_recurrence(issue, issue_url, candidates, force_improvement=force_improvement)

    def generate_technical_change_proposal(
        self,
        *,
        improvement: ImprovementSummary,
        issues: list[SystemIssueSummary],
        candidate_files: list[str],
        repository_context: dict[str, str],
    ) -> TechnicalChangeProposal:
        if not self.api_key:
            raise RuntimeError("AI-анализ недоступен")
        system = (
            "Ты готовишь ограниченное техническое задание для Codex по подтвержденному Improvement. "
            "Не предлагай запуск Codex, создание branch, commit или PR. "
            "Candidate files должны быть только из переданного списка. "
            "Формулируй предполагаемую причину как гипотезу, а не установленный факт. "
            "Добавь положительные и отрицательные regression tests."
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "improvement": improvement.__dict__,
                            "system_issues": [issue.__dict__ for issue in issues],
                            "candidate_files": candidate_files,
                            "repository_context": repository_context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conductor_technical_change_proposal",
                    "schema": TECHNICAL_CHANGE_PROPOSAL_SCHEMA,
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
        return technical_change_proposal_from_dict(json.loads(_extract_response_text(data)))

    def enrich_feedback(
        self,
        *,
        raw_text: str,
        deterministic: Any,
        interaction: dict[str, Any],
    ) -> FeedbackEnrichment:
        if not self.api_key:
            raise RuntimeError("AI-анализ недоступен")
        system = (
            "Ты нормализуешь пользовательский feedback для backlog. "
            "Не меняй смысл исходного текста, не выдумывай факты, перечисляй evidence и inferred_fields. "
            "CORRECTION не должен попадать в backlog, NOT_FEEDBACK не создает System Issue."
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "raw_feedback": raw_text,
                            "deterministic": deterministic.__dict__,
                            "interaction": interaction,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conductor_feedback_enrichment",
                    "schema": FEEDBACK_ENRICHMENT_SCHEMA,
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
        return feedback_enrichment_from_dict(json.loads(_extract_response_text(data)))

    def match_improvements(
        self,
        *,
        feedback: Any,
        candidates: list[ImprovementSummary],
    ) -> list[ImprovementMatchCandidate]:
        if not self.api_key:
            raise RuntimeError("AI-анализ недоступен")
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Сравни normalized feedback с открытыми Improvements. "
                        "SAME_PROBLEM только если это одна системная причина или одно ожидаемое изменение. "
                        "Одна база, компонент или общее слово недостаточны."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "feedback": feedback.__dict__,
                            "candidates": [candidate.__dict__ for candidate in candidates[:10]],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conductor_improvement_match",
                    "schema": IMPROVEMENT_MATCH_SCHEMA,
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
        raw = json.loads(_extract_response_text(data))
        return [improvement_match_candidate_from_dict(item) for item in raw.get("candidates", [])]

    def assess_improvement_pairs(self, *, pairs: list[dict[str, Any]]) -> list[ImprovementPairAssessment]:
        if not self.api_key:
            raise RuntimeError("AI-анализ недоступен")
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Сравни пары Improvements. SAME_PROBLEM только если это одна проблема и одно ожидаемое изменение. "
                        "Даже при высокой уверенности возвращай только рекомендацию, без команды merge."
                    ),
                },
                {"role": "user", "content": json.dumps({"pairs": pairs[:30]}, ensure_ascii=False)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "conductor_improvement_pair_assessment",
                    "schema": IMPROVEMENT_PAIR_ASSESSMENT_SCHEMA,
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
        raw = json.loads(_extract_response_text(data))
        return [improvement_pair_assessment_from_dict(item) for item in raw.get("pairs", [])]

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
            "покрыш",
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
        if any(word in lower for word in goods_words) and not _looks_like_non_goods_request(text):
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
    url = _extract_url(value)
    if url:
        value = value.replace(url, "")
    return _capitalize_first_letter(_first_sentence(value).strip(" .,\n\t")[:120])


def _looks_like_non_goods_request(text: str) -> bool:
    lower = text.casefold()
    if re.search(r"\bкупить\s+время\b", lower):
        return True
    action_markers = ("заказать", "закажи", "выбрать", "выбери", "нужен", "нужна", "нужно")
    non_goods_markers = ("встреч", "созвон", "звонок", "разговор")
    return any(action in lower for action in action_markers) and any(marker in lower for marker in non_goods_markers)


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


def _fallback_system_issue_classification(original_text: str, actual_context: dict[str, Any], correction: str):
    from .models import SystemIssueClassification

    lower = correction.casefold()
    issue_type = "Неверная классификация"
    if "цен" in lower or "валют" in lower or "пол" in lower:
        issue_type = "Неверное извлечение поля"
    if "баз" in lower:
        issue_type = "Неверная база"
    if "не созд" in lower or "нужно было создать" in lower:
        issue_type = "Не создана нужная запись"
    if "дублик" in lower:
        issue_type = "Создан дубликат"
    if "потер" in lower:
        issue_type = "Потеря информации"
    if "не ту" in lower or "не та" in lower:
        issue_type = "Обновлена не та запись"
    if "ничего создавать" in lower or "не надо создавать" in lower or "не нужно создавать" in lower:
        issue_type = "Неверное выполнение команды"

    severity = "Средняя"
    if issue_type in {"Потеря информации", "Обновлена не та запись"}:
        severity = "Высокая"
    if "лишн" in lower or "уточнен" in lower or "вопрос" in lower:
        severity = "Низкая"

    database = "Другое"
    combined = f"{original_text} {correction}".casefold()
    if "товар" in combined or "goods" in combined or "покуп" in combined or "покрыш" in combined:
        database = "BUY"
    elif "study" in combined or "изуч" in combined:
        database = "Study / На изучение"
    elif "task" in combined or "задач" in combined:
        database = "TASKS"

    correction_intent = "UNKNOWN"
    target_type = "Unknown"
    corrected_fields: list[str] = []
    if any(marker in lower for marker in ("это задача", "нужно было создать задачу")):
        correction_intent = "CHANGE_ENTITY_TYPE"
        target_type = "Task"
    elif any(marker in lower for marker in ("это товар", "goods", "buy")):
        correction_intent = "CHANGE_ENTITY_TYPE"
        target_type = "Goods"
    elif any(marker in lower for marker in ("это исследование", "это study", "на изучение")):
        correction_intent = "CHANGE_ENTITY_TYPE"
        target_type = "Study"
    elif any(marker in lower for marker in ("ничего создавать", "не надо создавать", "не нужно создавать", "просто комментарий")):
        correction_intent = "NO_ACTION_EXPECTED"
        target_type = "None"
    elif "ты не создал" in lower or "ты не создала" in lower or "не создан" in lower:
        correction_intent = "CREATE_MISSING_RECORD"
    elif "не ту" in lower or "не та" in lower:
        correction_intent = "UPDATE_WRONG_RECORD"
    elif any(marker in lower for marker in ("дата", "завтра", "сегодня", "послезавтра")):
        correction_intent = "CHANGE_FIELDS"
        corrected_fields.append("date")
    elif any(marker in lower for marker in ("время", "15:00", "час")):
        correction_intent = "CHANGE_FIELDS"
        corrected_fields.append("time")
    elif "проект" in lower:
        correction_intent = "CHANGE_FIELDS"
        corrected_fields.append("project")

    title = original_text.strip()[:120] or correction.strip()[:120] or "Ошибка Дирижера"
    return SystemIssueClassification(
        issue_type=issue_type,
        severity=severity,
        database=database,
        actual_result=_summarize_actual_context(actual_context),
        expected_result=correction.strip(),
        probable_cause="Техническая причина требует анализа",
        title=title,
        correction_intent=correction_intent,
        correction_target_type=target_type,
        corrected_fields=corrected_fields,
        should_delete_original=correction_intent in {"DELETE_OR_CANCEL", "NO_ACTION_EXPECTED"},
        needs_user_clarification=correction_intent == "UNKNOWN",
        clarification_question="Как должно было быть правильно?" if correction_intent == "UNKNOWN" else "",
    )


def _fallback_issue_recurrence(
    issue: SystemIssueRecord,
    issue_url: str,
    candidates: list[SystemIssueSummary],
    *,
    force_improvement: bool,
) -> IssueRecurrenceAnalysis:
    direction = _issue_direction(issue)
    related = [
        candidate.url
        for candidate in candidates
        if candidate.url
        and candidate.url != issue_url
        and candidate.issue_type == issue.classification.issue_type
        and candidate.database == issue.classification.database
        and direction
        and _summary_direction(candidate) == direction
    ]
    should_offer = len(related) >= 2 or (len(related) >= 1 and issue.classification.severity == "Высокая") or force_improvement
    priority = "Средний"
    if issue.classification.severity == "Высокая" or len(related) >= 3:
        priority = "Высокий"
    elif not related:
        priority = "Низкий"
    title = _fallback_improvement_title(issue, direction)
    return IssueRecurrenceAnalysis(
        is_recurring=should_offer,
        related_issue_urls=related,
        recurrence_group_title=title if should_offer else "",
        similarity_reason=(
            f"Одинаковые тип ошибки, база и направление исправления: {direction}."
            if direction and related
            else "Детерминированная группировка не нашла достаточной содержательной близости."
        ),
        confidence=0.65 if should_offer else 0.0,
        suggested_improvement_title=title if should_offer else "",
        suggested_improvement_description=(
            f"Обнаружены похожие ошибки типа «{issue.classification.issue_type}» в базе «{issue.classification.database}»."
            if should_offer
            else ""
        ),
        suggested_change=(
            "Проверить и уточнить правила классификации/маршрутизации для этого направления исправления. "
            "Добавить regression-тесты на найденные примеры."
            if should_offer
            else ""
        ),
        improvement_type="Правило",
        change_location="Правила Дирижёра",
        priority=priority,
    )


def _issue_for_recurrence(issue: SystemIssueRecord, issue_url: str) -> dict[str, Any]:
    return {
        "url": issue_url,
        "issue_type": issue.classification.issue_type,
        "severity": issue.classification.severity,
        "database": issue.classification.database,
        "actual_result": issue.classification.actual_result,
        "expected_result": issue.classification.expected_result,
        "correction_intent": issue.classification.correction_intent,
        "correction_target_type": issue.classification.correction_target_type,
        "corrected_fields": issue.classification.corrected_fields,
        "input_data": issue.input_data,
        "description": issue.description,
    }


def _candidate_for_recurrence(candidate: SystemIssueSummary) -> dict[str, Any]:
    return {
        "url": candidate.url,
        "title": candidate.title,
        "issue_type": candidate.issue_type,
        "severity": candidate.severity,
        "database": candidate.database,
        "input_data": candidate.input_data,
        "description": candidate.description,
        "solution": candidate.solution,
        "detected_date": candidate.detected_date,
    }


def _issue_direction(issue: SystemIssueRecord) -> str:
    classification = issue.classification
    if classification.correction_intent == "CHANGE_ENTITY_TYPE" and classification.correction_target_type:
        source = _infer_actual_entity_type(classification.actual_result)
        return f"{source}->{classification.correction_target_type}" if source else f"->{classification.correction_target_type}"
    if classification.corrected_fields:
        return ",".join(sorted(field.casefold() for field in classification.corrected_fields))
    if classification.correction_intent in {"CREATE_MISSING_RECORD", "UPDATE_WRONG_RECORD", "NO_ACTION_EXPECTED"}:
        return classification.correction_intent
    return ""


def _summary_direction(candidate: SystemIssueSummary) -> str:
    combined = " ".join([candidate.title, candidate.description, candidate.solution, candidate.input_data]).casefold()
    if _mentions_any(combined, ("study", "изучение")) and _mentions_any(combined, ("goods", "товар", "buy", "покуп")):
        return "Study->Goods"
    if _mentions_any(combined, ("task", "задач")) and _mentions_any(combined, ("goods", "товар", "buy", "покуп")):
        return "Task->Goods"
    if _mentions_any(combined, ("goods", "товар", "buy", "покуп")) and _mentions_any(combined, ("study", "изучение")):
        return "Goods->Study"
    if _mentions_any(combined, ("date", "дата", "срок", "завтра", "сегодня")):
        return "date"
    if _mentions_any(combined, ("time", "время", "час", "15:00")):
        return "time"
    if _mentions_any(combined, ("project", "проект")):
        return "project"
    if "не создан" in combined or "не создала" in combined:
        return "CREATE_MISSING_RECORD"
    if "не ту" in combined or "не та запись" in combined:
        return "UPDATE_WRONG_RECORD"
    if "ничего создавать" in combined or "не надо создавать" in combined:
        return "NO_ACTION_EXPECTED"
    return ""


def _infer_actual_entity_type(actual_result: str) -> str:
    lower = actual_result.casefold()
    for entity, key in (("Task", "tasks"), ("Study", "studies"), ("Goods", "goods")):
        match = re.search(rf'"{key}"\s*:\s*([1-9]\d*)', lower)
        if match:
            return entity
    counts = {
        "Task": _count_entity(lower, "tasks", "задач", "task"),
        "Study": _count_entity(lower, "studies", "изуч", "study"),
        "Goods": _count_entity(lower, "goods", "товар", "buy"),
    }
    entity, count = max(counts.items(), key=lambda item: item[1])
    return entity if count > 0 else ""


def _count_entity(text: str, *markers: str) -> int:
    return sum(text.count(marker) for marker in markers)


def _mentions_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _fallback_improvement_title(issue: SystemIssueRecord, direction: str) -> str:
    if direction.endswith("->Goods") or issue.classification.database == "BUY":
        return "Уточнить классификацию товаров"
    if "date" in direction:
        return "Уточнить извлечение дат"
    if "time" in direction:
        return "Уточнить извлечение времени"
    return f"Уточнить обработку ошибок: {issue.classification.issue_type}"


def _summarize_actual_context(actual_context: dict[str, Any]) -> str:
    parts = []
    if actual_context.get("classification"):
        classification = actual_context["classification"]
        parts.append(
            "classification="
            + json.dumps(
                {
                    "tasks": len(classification.get("tasks", [])),
                    "studies": len(classification.get("studies", [])),
                    "goods": len(classification.get("goods", [])),
                },
                ensure_ascii=False,
            )
        )
    if actual_context.get("created"):
        parts.append("created=" + json.dumps(actual_context["created"], ensure_ascii=False))
    if actual_context.get("pending"):
        parts.append("pending=" + json.dumps(actual_context["pending"], ensure_ascii=False))
    if actual_context.get("errors"):
        parts.append("errors=" + json.dumps(actual_context["errors"], ensure_ascii=False))
    return "; ".join(parts) or "Требуется анализ"


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
