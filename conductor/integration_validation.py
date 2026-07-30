from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .feedback_backlog import normalize_feedback
from .models import (
    IntegrationValidationResult,
    ImprovementSummary,
    SystemIssueSummary,
    technical_change_proposal_from_dict,
)


SYSTEM_ISSUES_SCHEMA = {
    "Краткое описание ошибки": "title",
    "Входные данные": "rich_text",
    "Описание": "rich_text",
    "Тип ошибки": "select",
    "Критичность": "select",
    "Статус": "select",
    "Способ обнаружения": "select",
    "Причина ошибки": "rich_text",
    "Решение": "rich_text",
    "Дата обнаружения": "date",
}

IMPROVEMENTS_SCHEMA = {
    "Улучшение": "title",
    "Описание": "rich_text",
    "Что изменить": "rich_text",
    "Тип улучшения": "select",
    "Где изменить": "select",
    "Приоритет": "select",
    "Статус": "select",
    "Какие ошибки исправляет": "relation",
    "Дата внедрения": "date",
    "Результат": "rich_text",
}


def validate_feedback_backlog_schema(notion: Any) -> list[IntegrationValidationResult]:
    print("BACKLOG_PRODUCTION_VALIDATION_STARTED state=notion_schema", flush=True)
    results = [
        _validate_database(notion, "Notion SYSTEM ISSUES", getattr(notion, "system_issues_db", ""), SYSTEM_ISSUES_SCHEMA),
        _validate_database(notion, "Notion IMPROVEMENTS", getattr(notion, "improvements_db", ""), IMPROVEMENTS_SCHEMA),
    ]
    if any(not item.valid for item in results):
        print("NOTION_SCHEMA_VALIDATION_FAILED", flush=True)
    print("BACKLOG_PRODUCTION_VALIDATION_COMPLETED state=notion_schema", flush=True)
    return results


def validate_openai_contracts(openai: Any) -> list[IntegrationValidationResult]:
    print("BACKLOG_PRODUCTION_VALIDATION_STARTED state=openai_contract", flush=True)
    checks = [
        ("OpenAI enrichment contract", _check_enrichment),
        ("OpenAI semantic matching contract", _check_match),
        ("OpenAI Technical Spec contract", _check_technical_spec),
    ]
    results = []
    for name, check in checks:
        try:
            errors = check(openai)
            results.append(_result(name, not errors, errors, []))
        except Exception as exc:  # noqa: BLE001
            print(f"OPENAI_CONTRACT_VALIDATION_FAILED integration={name} error={type(exc).__name__}", flush=True)
            results.append(_result(name, False, [str(exc)], []))
    print("BACKLOG_PRODUCTION_VALIDATION_COMPLETED state=openai_contract", flush=True)
    return results


def _validate_database(notion: Any, name: str, database_id: str, expected: dict[str, str]) -> IntegrationValidationResult:
    if not database_id:
        return _result(name, False, ["database id is not configured"], [])
    try:
        schema = notion.retrieve_database(database_id)
    except Exception as exc:  # noqa: BLE001
        return _result(name, False, [f"database read failed: {exc}"], [])
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    errors = []
    for prop_name, prop_type in expected.items():
        actual = (props.get(prop_name) or {}).get("type")
        if not actual:
            errors.append(f"Missing property: {prop_name}")
        elif actual != prop_type:
            errors.append(f"Несовместимое поле: «{prop_name}» — ожидался {prop_type}, получен {actual}.")
    return _result(name, not errors, errors, [])


def _check_enrichment(openai: Any) -> list[str]:
    feedback = normalize_feedback("[SMOKE TEST] Ты часто теряешь даты")
    enrichment = openai.enrich_feedback(raw_text="[SMOKE TEST] Ты часто теряешь даты", deterministic=feedback, interaction={})
    errors = []
    if enrichment.feedback_kind not in {"CONCRETE_ERROR", "GENERAL_PROBLEM", "IMPROVEMENT_IDEA", "CORRECTION", "NOT_FEEDBACK", "UNKNOWN"}:
        errors.append("unsupported feedback_kind")
    if not 0 <= enrichment.confidence <= 1:
        errors.append("confidence out of range")
    return errors


def _check_match(openai: Any) -> list[str]:
    feedback = normalize_feedback("[SMOKE TEST] Ты часто теряешь даты")
    candidate = ImprovementSummary(
        page_id="00000000-0000-0000-0000-000000000001",
        url="https://www.notion.so/00000000000000000000000000000001",
        title="[SMOKE TEST] Даты теряются",
        status="Идея",
        improvement_type="Правило",
        change_location="Правила Дирижёра",
        description="Синтетическая проверка.",
        suggested_change="Система должна сохранять даты.",
    )
    matches = openai.match_improvements(feedback=feedback, candidates=[candidate])
    errors = []
    for match in matches:
        if match.improvement_id != candidate.page_id:
            errors.append("unexpected candidate id")
        if not 0 <= match.score <= 100:
            errors.append("match score out of range")
    return errors


def _check_technical_spec(openai: Any) -> list[str]:
    improvement = ImprovementSummary(
        page_id="00000000-0000-0000-0000-000000000001",
        url="https://www.notion.so/00000000000000000000000000000001",
        title="[SMOKE TEST] Даты теряются",
        status="Идея",
        improvement_type="Правило",
        change_location="Правила Дирижёра",
        related_issue_urls=["00000000-0000-0000-0000-000000000002"],
        description="Синтетическая проверка.",
        suggested_change="Система должна сохранять даты.",
    )
    issue = SystemIssueSummary(
        page_id="00000000-0000-0000-0000-000000000002",
        url="https://www.notion.so/00000000000000000000000000000002",
        title="[SMOKE TEST] Дата потеряна",
        issue_type="Неверная дата",
        severity="Средняя",
        database="TASKS",
        input_data="[SMOKE TEST]",
        description="Синтетическая проверка.",
        solution="Требуется анализ.",
        detected_date="2026-07-30",
    )
    proposal = openai.generate_technical_change_proposal(improvement=improvement, issues=[issue], candidate_files=[], repository_context={})
    parsed = technical_change_proposal_from_dict(proposal.__dict__)
    errors = []
    if not parsed.problem_statement:
        errors.append("empty problem_statement")
    if not 0 <= parsed.confidence <= 1:
        errors.append("confidence out of range")
    return errors


def _result(integration: str, valid: bool, errors: list[str], warnings: list[str]) -> IntegrationValidationResult:
    return IntegrationValidationResult(integration, valid, errors, warnings, datetime.now(timezone.utc).isoformat())
