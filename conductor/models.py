from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


AREAS = {"Работа", "Бизнес", "Личное развитие", "Семья", "Прочее"}
TASK_PRIORITIES = {"P1", "P2", "P3"}
PROJECT_PRIORITIES = {"P1", "P2", "P3", "P4"}
RESEARCH_TYPES = {"Простое", "Глубокое"}
RESULT_FORMATS = {"Краткая справка", "Подробная справка", "Memo", "Таблица", "Telegram-дайджест"}
GOODS_STATUSES = {"Не куплено", "Необходимо выбрать", "В процессе", "Необходимо одобрить выбор", "Куплено"}
GOODS_TYPES = {
    "Техника/электроника",
    "Дом/быт",
    "Одежда/обувь",
    "Здоровье/красота",
    "Еда/напитки",
    "Хобби/спорт",
    "Подарок",
    "Другое",
}
GOODS_CURRENCIES = {"MXN", "USD", "EUR", "RUB"}
GOODS_USERS = {"Личное", "Семья", "Ребёнок", "Партнёр/партнёрша", "Дом", "Работа", "Подарок", "Другое"}
GOODS_USAGE_PLACES = {"Дом", "Офис", "Поездки", "Подарок", "Другое"}
SYSTEM_ISSUE_TYPES = {
    "Неверная классификация",
    "Неверная база",
    "Неверное извлечение поля",
    "Неверная дата",
    "Неверное время",
    "Неверная длительность",
    "Потеря информации",
    "Создан дубликат",
    "Обновлена не та запись",
    "Не создана нужная запись",
    "Не обновлена нужная запись",
    "Неверная связь",
    "Отсутствующая связь",
    "Галлюцинация значения",
    "Игнорирование команды",
    "Неверное выполнение команды",
    "Неполный отчёт",
    "Другое",
}
SYSTEM_ISSUE_SEVERITIES = {"Высокая", "Средняя", "Низкая"}
SYSTEM_ISSUE_DATABASES = {
    "TASKS",
    "PROBLEMS",
    "Study / На изучение",
    "EVENTS",
    "IDEAS",
    "COMMUNICATIONS",
    "CONTACTS",
    "FILMS",
    "BOOKS",
    "BUY",
    "SUBSCRIPTIONS",
    "Другое",
}
CORRECTION_INTENTS = {
    "CHANGE_ENTITY_TYPE",
    "CHANGE_FIELDS",
    "DELETE_OR_CANCEL",
    "CREATE_MISSING_RECORD",
    "UPDATE_WRONG_RECORD",
    "NO_ACTION_EXPECTED",
    "UNKNOWN",
}
CORRECTION_TARGET_TYPES = {"Task", "Study", "Goods", "Event", "Other", "None", "Unknown"}
IMPROVEMENT_TYPES = {"Правило", "Промпт", "Архитектура", "Поля базы", "Интеграция", "Автоматизация"}
IMPROVEMENT_CHANGE_LOCATIONS = {
    "Правила Дирижёра",
    "Правила Любы",
    "Notion",
    "Todoist",
    "Google Calendar",
    "Telegram",
    "Другое",
}
IMPROVEMENT_PRIORITIES = {"Высокий", "Средний", "Низкий"}
IMPROVEMENT_OPEN_STATUSES = {"Идея", "В работе", "Отложено"}


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
class GoodsItem:
    title: str
    status: str | None
    goods_type: str | None
    priority: str | None
    price: float | None
    currency: str | None
    goods_user: str | None
    usage_place: str | None
    stream: str | None
    project: str | None
    url: str | None
    source: str | None
    confidence: float
    missing: list[str] = field(default_factory=list)


@dataclass
class Classification:
    tasks: list[TaskItem]
    studies: list[StudyItem]
    goods: list[GoodsItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class SystemIssueClassification:
    issue_type: str
    severity: str
    database: str
    actual_result: str
    expected_result: str
    probable_cause: str
    title: str
    correction_intent: str = "UNKNOWN"
    correction_target_type: str = "Unknown"
    corrected_fields: list[str] = field(default_factory=list)
    should_delete_original: bool = False
    needs_user_clarification: bool = False
    clarification_question: str = ""


@dataclass
class SystemIssueRecord:
    classification: SystemIssueClassification
    detection_method: str
    status: str
    input_data: str
    description: str
    solution: str
    detected_date: str
    fingerprint: str


@dataclass
class SystemIssueSummary:
    page_id: str
    url: str
    title: str
    issue_type: str
    severity: str
    database: str
    input_data: str
    description: str
    solution: str
    detected_date: str


@dataclass
class ImprovementRecord:
    title: str
    description: str
    suggested_change: str
    improvement_type: str
    change_location: str
    priority: str
    status: str = "Идея"


@dataclass
class ImprovementSummary:
    page_id: str
    url: str
    title: str
    status: str
    improvement_type: str
    change_location: str
    related_issue_urls: list[str] = field(default_factory=list)
    priority: str = ""
    description: str = ""
    suggested_change: str = ""


@dataclass
class IssueRecurrenceAnalysis:
    is_recurring: bool
    related_issue_urls: list[str]
    recurrence_group_title: str
    similarity_reason: str
    confidence: float
    suggested_improvement_title: str
    suggested_improvement_description: str
    suggested_change: str
    improvement_type: str
    change_location: str
    priority: str


@dataclass
class TechnicalChangeProposal:
    improvement_title: str
    problem_statement: str
    evidence_summary: str
    desired_behavior: str
    current_behavior: str
    likely_root_cause: str
    change_type: str
    affected_components: list[str]
    candidate_files: list[str]
    required_changes: list[str]
    regression_tests: list[str]
    acceptance_criteria: list[str]
    out_of_scope: list[str]
    risks: list[str]
    open_questions: list[str]
    confidence: float


@dataclass
class NormalizedFeedback:
    feedback_kind: str
    normalized_title: str
    normalized_description: str
    original_text: str
    actual_behavior: str
    expected_behavior: str
    affected_entity_type: str
    affected_database: str
    affected_component: str
    severity: str
    is_recurring_statement: bool
    needs_interaction_context: bool
    should_create_system_issue: bool
    should_find_or_create_improvement: bool
    proposed_improvement_title: str
    proposed_improvement_description: str
    confidence: float
    needs_clarification: bool
    clarification_question: str


@dataclass
class FeedbackEnrichment:
    feedback_kind: str
    normalized_title: str
    normalized_description: str
    actual_behavior: str
    expected_behavior: str
    affected_entity_type: str
    affected_database: str
    affected_component: str
    severity: str
    is_recurring_statement: bool
    should_create_system_issue: bool
    should_find_or_create_improvement: bool
    proposed_improvement_title: str
    proposed_improvement_description: str
    confidence: float
    inferred_fields: list[str]
    evidence: list[str]
    needs_clarification: bool
    clarification_question: str


@dataclass
class BacklogPriorityRecommendation:
    recommended_priority: str
    score: int
    reasons: list[str]


@dataclass
class ImprovementMatchCandidate:
    improvement_id: str
    score: int
    relation_type: str
    reasons: list[str]
    contradictions: list[str]


@dataclass
class BacklogReadiness:
    status: str
    score: int
    reasons: list[str]
    missing_information: list[str]


@dataclass
class BacklogMergeProposal:
    primary_improvement_id: str
    secondary_improvement_id: str
    primary_title: str
    secondary_title: str
    relation_ids_to_keep: list[str]
    reasons: list[str]


@dataclass
class BacklogSplitProposal:
    improvement_id: str
    current_title: str
    suggested_titles: list[str]
    reasons: list[str]


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


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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

    goods = []
    for item in data.get("goods", []) or []:
        goods.append(
            GoodsItem(
                title=str(item.get("title") or "").strip(),
                status=_as_optional_str(item.get("status")),
                goods_type=_as_optional_str(item.get("goods_type")),
                priority=_as_optional_str(item.get("priority")),
                price=_as_number(item.get("price")),
                currency=_as_optional_str(item.get("currency")),
                goods_user=_as_optional_str(item.get("goods_user")),
                usage_place=_as_optional_str(item.get("usage_place")),
                stream=_as_optional_str(item.get("stream")),
                project=_as_optional_str(item.get("project")),
                url=_as_optional_str(item.get("url")),
                source=_as_optional_str(item.get("source")),
                confidence=_as_float(item.get("confidence"), 0.0),
                missing=[str(x) for x in item.get("missing", [])],
            )
        )

    return Classification(tasks=tasks, studies=studies, goods=goods, notes=[str(x) for x in data.get("notes", [])])


def system_issue_classification_from_dict(data: dict[str, Any]) -> SystemIssueClassification:
    issue_type = str(data.get("issue_type") or "Неверная классификация").strip()
    severity = str(data.get("severity") or "Средняя").strip()
    database = str(data.get("database") or "Другое").strip()
    correction_intent = str(data.get("correction_intent") or "UNKNOWN").strip()
    correction_target_type = str(data.get("correction_target_type") or "Unknown").strip()
    return SystemIssueClassification(
        issue_type=issue_type if issue_type in SYSTEM_ISSUE_TYPES else "Другое",
        severity=severity if severity in SYSTEM_ISSUE_SEVERITIES else "Средняя",
        database=database if database in SYSTEM_ISSUE_DATABASES else "Другое",
        actual_result=str(data.get("actual_result") or "").strip(),
        expected_result=str(data.get("expected_result") or "").strip(),
        probable_cause=str(data.get("probable_cause") or "Требуется анализ").strip() or "Требуется анализ",
        title=str(data.get("title") or "").strip(),
        correction_intent=correction_intent if correction_intent in CORRECTION_INTENTS else "UNKNOWN",
        correction_target_type=correction_target_type if correction_target_type in CORRECTION_TARGET_TYPES else "Unknown",
        corrected_fields=[str(value) for value in data.get("corrected_fields", [])],
        should_delete_original=bool(data.get("should_delete_original", False)),
        needs_user_clarification=bool(data.get("needs_user_clarification", False)),
        clarification_question=str(data.get("clarification_question") or "").strip(),
    )


def issue_recurrence_analysis_from_dict(data: dict[str, Any]) -> IssueRecurrenceAnalysis:
    improvement_type = str(data.get("improvement_type") or "Правило").strip()
    change_location = str(data.get("change_location") or "Правила Дирижёра").strip()
    priority = str(data.get("priority") or "Средний").strip()
    confidence = max(0.0, min(_as_float(data.get("confidence"), 0.0), 1.0))
    return IssueRecurrenceAnalysis(
        is_recurring=bool(data.get("is_recurring", False)),
        related_issue_urls=[str(value) for value in data.get("related_issue_urls", []) if str(value).strip()],
        recurrence_group_title=str(data.get("recurrence_group_title") or "").strip(),
        similarity_reason=str(data.get("similarity_reason") or "").strip(),
        confidence=confidence,
        suggested_improvement_title=str(data.get("suggested_improvement_title") or "").strip(),
        suggested_improvement_description=str(data.get("suggested_improvement_description") or "").strip(),
        suggested_change=str(data.get("suggested_change") or "").strip(),
        improvement_type=improvement_type if improvement_type in IMPROVEMENT_TYPES else "Правило",
        change_location=change_location if change_location in IMPROVEMENT_CHANGE_LOCATIONS else "Правила Дирижёра",
        priority=priority if priority in IMPROVEMENT_PRIORITIES else "Средний",
    )


def technical_change_proposal_from_dict(data: dict[str, Any]) -> TechnicalChangeProposal:
    return TechnicalChangeProposal(
        improvement_title=str(data.get("improvement_title") or "").strip(),
        problem_statement=str(data.get("problem_statement") or "").strip(),
        evidence_summary=str(data.get("evidence_summary") or "").strip(),
        desired_behavior=str(data.get("desired_behavior") or "").strip(),
        current_behavior=str(data.get("current_behavior") or "").strip(),
        likely_root_cause=str(data.get("likely_root_cause") or "").strip(),
        change_type=str(data.get("change_type") or "").strip(),
        affected_components=[str(value) for value in data.get("affected_components", []) if str(value).strip()],
        candidate_files=[str(value) for value in data.get("candidate_files", []) if str(value).strip()],
        required_changes=[str(value) for value in data.get("required_changes", []) if str(value).strip()],
        regression_tests=[str(value) for value in data.get("regression_tests", []) if str(value).strip()],
        acceptance_criteria=[str(value) for value in data.get("acceptance_criteria", []) if str(value).strip()],
        out_of_scope=[str(value) for value in data.get("out_of_scope", []) if str(value).strip()],
        risks=[str(value) for value in data.get("risks", []) if str(value).strip()],
        open_questions=[str(value) for value in data.get("open_questions", []) if str(value).strip()],
        confidence=max(0.0, min(_as_float(data.get("confidence"), 0.0), 1.0)),
    )


def feedback_enrichment_from_dict(data: dict[str, Any]) -> FeedbackEnrichment:
    return FeedbackEnrichment(
        feedback_kind=str(data.get("feedback_kind") or "UNKNOWN").strip(),
        normalized_title=str(data.get("normalized_title") or "").strip(),
        normalized_description=str(data.get("normalized_description") or "").strip(),
        actual_behavior=str(data.get("actual_behavior") or "").strip(),
        expected_behavior=str(data.get("expected_behavior") or "").strip(),
        affected_entity_type=str(data.get("affected_entity_type") or "Unknown").strip(),
        affected_database=str(data.get("affected_database") or "Другое").strip(),
        affected_component=str(data.get("affected_component") or "Другое").strip(),
        severity=str(data.get("severity") or "Средняя").strip(),
        is_recurring_statement=bool(data.get("is_recurring_statement", False)),
        should_create_system_issue=bool(data.get("should_create_system_issue", False)),
        should_find_or_create_improvement=bool(data.get("should_find_or_create_improvement", False)),
        proposed_improvement_title=str(data.get("proposed_improvement_title") or "").strip(),
        proposed_improvement_description=str(data.get("proposed_improvement_description") or "").strip(),
        confidence=max(0.0, min(_as_float(data.get("confidence"), 0.0), 1.0)),
        inferred_fields=[str(value) for value in data.get("inferred_fields", []) if str(value).strip()],
        evidence=[str(value) for value in data.get("evidence", []) if str(value).strip()],
        needs_clarification=bool(data.get("needs_clarification", False)),
        clarification_question=str(data.get("clarification_question") or "").strip(),
    )


def improvement_match_candidate_from_dict(data: dict[str, Any]) -> ImprovementMatchCandidate:
    return ImprovementMatchCandidate(
        improvement_id=str(data.get("improvement_id") or "").strip(),
        score=max(0, min(_as_int(data.get("score")) or 0, 100)),
        relation_type=str(data.get("relation_type") or "NOT_RELATED").strip(),
        reasons=[str(value) for value in data.get("reasons", []) if str(value).strip()],
        contradictions=[str(value) for value in data.get("contradictions", []) if str(value).strip()],
    )
