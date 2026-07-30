from __future__ import annotations

import re
from datetime import date
from typing import Any

from .models import BacklogPriorityRecommendation, ImprovementSummary, NormalizedFeedback, SystemIssueClassification, SystemIssueRecord


FEEDBACK_KINDS = {"CONCRETE_ERROR", "GENERAL_PROBLEM", "IMPROVEMENT_IDEA", "CORRECTION", "NOT_FEEDBACK", "UNKNOWN"}


def normalize_feedback(text: str, *, interaction: dict[str, Any] | None = None) -> NormalizedFeedback:
    original = text.strip()
    normalized = " ".join(original.casefold().split())
    context = interaction or {}
    is_reply_context = bool(context)
    if not normalized:
        return _feedback("NOT_FEEDBACK", original, "Пустая обратная связь", confidence=0.0)
    if _is_neutral_reply(normalized):
        return _feedback(
            "NOT_FEEDBACK",
            original,
            "Нейтральный ответ пользователя",
            normalized_description="Пользователь подтвердил или поблагодарил. Это не системная ошибка.",
            should_create_system_issue=False,
            should_find_or_create_improvement=False,
            confidence=0.95,
        )
    if _is_correction(normalized):
        return _feedback(
            "CORRECTION",
            original,
            "Исправление текущего результата",
            normalized_description="Пользователь просит исправить текущий результат. Обработка остается в correction flow.",
            should_create_system_issue=False,
            should_find_or_create_improvement=False,
            confidence=0.75,
        )
    if _is_ambiguous(normalized) and not is_reply_context:
        return _feedback(
            "UNKNOWN",
            original,
            "Неоднозначная обратная связь",
            needs_clarification=True,
            clarification_question=(
                "К какому результату относится ошибка?\n\n"
                "Ответь Reply на сообщение Любы\n"
                "или кратко опиши, что было сделано неправильно."
            ),
            confidence=0.35,
        )
    if _is_idea(normalized):
        title = _idea_title(normalized)
        return _feedback(
            "IMPROVEMENT_IDEA",
            original,
            title,
            normalized_description=f"Пользователь предложил улучшение: {title}.",
            expected_behavior=_expected_from_text(normalized),
            affected_component=_component_from_text(normalized),
            should_create_system_issue=False,
            should_find_or_create_improvement=True,
            proposed_improvement_title=title,
            proposed_improvement_description=f"Добавить в backlog идею пользователя: {title}.",
            confidence=0.72,
        )
    if _is_concrete_error(normalized):
        title = _problem_title(normalized, recurring=False)
        return _feedback(
            "CONCRETE_ERROR",
            original,
            title,
            normalized_description=_concrete_description(title, has_context=is_reply_context),
            actual_behavior=_actual_from_context(context) or _actual_from_text(normalized),
            expected_behavior=_expected_from_text(normalized),
            affected_entity_type=_entity_from_text(normalized),
            affected_database=_database_from_text(normalized),
            affected_component=_component_from_text(normalized),
            severity=_severity_from_text(normalized),
            needs_interaction_context=False,
            should_create_system_issue=True,
            should_find_or_create_improvement=True,
            proposed_improvement_title=_improvement_title_for(title),
            proposed_improvement_description=f"Снизить повторение ошибки: {title}.",
            confidence=0.68 if is_reply_context else 0.62,
        )
    if _is_general_problem(normalized):
        title = _problem_title(normalized, recurring=True)
        return _feedback(
            "GENERAL_PROBLEM",
            original,
            title,
            normalized_description=f"Пользователь описал повторяющуюся проблему: {title}. Конкретный interaction может отсутствовать.",
            expected_behavior=_expected_from_text(normalized),
            affected_entity_type=_entity_from_text(normalized),
            affected_database=_database_from_text(normalized),
            affected_component=_component_from_text(normalized),
            severity=_severity_from_text(normalized),
            is_recurring_statement=True,
            should_create_system_issue=False,
            should_find_or_create_improvement=True,
            proposed_improvement_title=_improvement_title_for(title),
            proposed_improvement_description=f"Накопить и проанализировать повторяющиеся сигналы: {title}.",
            confidence=0.70,
        )
    return _feedback("NOT_FEEDBACK", original, "Не обратная связь", should_find_or_create_improvement=False, confidence=0.2)


def build_feedback_system_issue(
    feedback: NormalizedFeedback,
    *,
    interaction: dict[str, Any] | None,
    today: str,
    corrected: bool = False,
) -> SystemIssueRecord:
    context = interaction or {}
    input_data = str(context.get("input_text") or "").strip() or "Не определено: feedback без привязки к конкретному interaction."
    description = "\n".join(
        [
            f"Исходный feedback: {feedback.original_text}",
            f"Нормализованное описание: {feedback.normalized_description}",
            f"Фактическое поведение: {feedback.actual_behavior or 'Не определено'}",
            f"Ожидаемое поведение: {feedback.expected_behavior or 'Не определено'}",
            f"Контекст interaction: {_interaction_context_summary(context)}",
        ]
    )
    solution = (
        "Конкретный результат исправлен по обратной связи пользователя.\nСистемная причина требует отдельного анализа."
        if corrected
        else "Не исправлено. Добавлено в backlog для анализа."
    )
    classification = SystemIssueClassification(
        issue_type=_issue_type(feedback),
        severity=feedback.severity if feedback.severity in {"Высокая", "Средняя", "Низкая"} else "Средняя",
        database=feedback.affected_database or "Другое",
        actual_result=feedback.actual_behavior,
        expected_result=feedback.expected_behavior,
        probable_cause="Требует анализа.",
        title=feedback.normalized_title,
        correction_intent="UNKNOWN",
        correction_target_type=feedback.affected_entity_type or "Unknown",
    )
    return SystemIssueRecord(
        classification=classification,
        detection_method="Пользователь",
        status="Новая",
        input_data=input_data,
        description=description,
        solution=solution,
        detected_date=today,
        fingerprint=_fingerprint(feedback.original_text, input_data, feedback.normalized_title),
    )


def score_improvement_match(improvement: ImprovementSummary, feedback: NormalizedFeedback) -> int:
    title = _tokens(improvement.title)
    proposed = _tokens(feedback.proposed_improvement_title or feedback.normalized_title)
    if not title or not proposed:
        return 0
    overlap = len(title & proposed)
    score = min(45, overlap * 12)
    if feedback.affected_component and feedback.affected_component.casefold() in improvement.change_location.casefold():
        score += 20
    if feedback.affected_database and feedback.affected_database.casefold() in (improvement.title + " " + improvement.description).casefold():
        score += 20
    if feedback.affected_entity_type and feedback.affected_entity_type.casefold() in improvement.title.casefold():
        score += 15
    if len(proposed) == 1 and score < 45:
        return 0
    return min(score, 100)


def choose_matching_improvement(
    candidates: list[ImprovementSummary],
    feedback: NormalizedFeedback,
    *,
    threshold: int = 60,
) -> ImprovementSummary | None:
    scored = [(score_improvement_match(item, feedback), item) for item in candidates]
    scored = [item for item in scored if item[0] >= threshold]
    return max(scored, key=lambda item: item[0])[1] if scored else None


def priority_recommendation(
    *,
    feedback: NormalizedFeedback,
    signal_count: int,
    explicit_request: bool = False,
) -> BacklogPriorityRecommendation:
    score = 20
    reasons = []
    if signal_count >= 4:
        score += 30
        reasons.append(f"проблема повторилась {signal_count} раза")
    elif signal_count >= 2:
        score += 18
        reasons.append(f"есть {signal_count} связанных сигнала")
    if feedback.severity == "Высокая":
        score += 25
        reasons.append("высокая критичность обратной связи")
    if feedback.affected_component in {"Telegram", "Notion", "Классификация"}:
        score += 15
        reasons.append("затрагивает основной маршрут Telegram -> Notion")
    if "потер" in feedback.original_text.casefold():
        score += 15
        reasons.append("есть риск потери данных")
    if explicit_request:
        score += 10
        reasons.append("пользователь явно попросил добавить в backlog")
    score = max(0, min(score, 100))
    if score >= 70:
        priority = "Высокий"
    elif score >= 40:
        priority = "Средний"
    else:
        priority = "Низкий"
    return BacklogPriorityRecommendation(priority, score, reasons or ["сигнал добавлен в backlog"])


def feedback_summary_markdown(
    *,
    signals: list[dict[str, Any]],
    related_issue_count: int,
    today: str,
) -> str:
    recent = signals[-20:]
    dates = [str(item.get("date") or "") for item in signals if item.get("date")]
    first = min(dates) if dates else today
    last = max(dates) if dates else today
    manifestations = _unique([str(item.get("title") or "Обратная связь") for item in signals])[:5]
    expected = _unique([str(item.get("expected") or "") for item in signals if item.get("expected")])[:5]
    concrete = sum(1 for item in signals if item.get("kind") == "CONCRETE_ERROR")
    general = sum(1 for item in signals if item.get("kind") == "GENERAL_PROBLEM")
    ideas = sum(1 for item in signals if item.get("kind") == "IMPROVEMENT_IDEA")
    lines = [
        "<!-- CONDUCTOR_FEEDBACK_SUMMARY_START -->",
        "",
        f"Количество связанных случаев: {related_issue_count}",
        f"Первый зафиксированный случай: {first}",
        f"Последний зафиксированный случай: {last}",
        "",
        "Основные проявления:",
        *[f"- {item}" for item in manifestations],
        "",
        "Ожидаемое поведение:",
        *[f"- {item}" for item in (expected or ["Требует уточнения по связанным сигналам"])],
        "",
        "Источники:",
        f"- конкретные System Issues: {concrete}",
        f"- общие наблюдения: {general}",
        f"- прямые идеи: {ideas}",
        "",
        "Дополнительные сигналы:",
        *[f"- {item.get('date') or today} — «{_short_signal(str(item.get('original') or ''))}»" for item in recent],
        "",
        f"Последнее обновление: {today}",
        "",
        "<!-- CONDUCTOR_FEEDBACK_SUMMARY_END -->",
    ]
    return "\n".join(lines)


def signal_payload(feedback: NormalizedFeedback, *, today: str, system_issue_url: str = "") -> dict[str, Any]:
    return {
        "date": today,
        "kind": feedback.feedback_kind,
        "title": feedback.normalized_title,
        "original": _short_signal(feedback.original_text),
        "expected": feedback.expected_behavior,
        "system_issue_url": system_issue_url,
    }


def _feedback(kind: str, original: str, title: str, **kwargs: Any) -> NormalizedFeedback:
    return NormalizedFeedback(
        feedback_kind=kind if kind in FEEDBACK_KINDS else "UNKNOWN",
        normalized_title=title,
        normalized_description=kwargs.get("normalized_description", title),
        original_text=original,
        actual_behavior=kwargs.get("actual_behavior", ""),
        expected_behavior=kwargs.get("expected_behavior", ""),
        affected_entity_type=kwargs.get("affected_entity_type", "Unknown"),
        affected_database=kwargs.get("affected_database", "Другое"),
        affected_component=kwargs.get("affected_component", "Другое"),
        severity=kwargs.get("severity", "Средняя"),
        is_recurring_statement=kwargs.get("is_recurring_statement", False),
        needs_interaction_context=kwargs.get("needs_interaction_context", False),
        should_create_system_issue=kwargs.get("should_create_system_issue", kind == "CONCRETE_ERROR"),
        should_find_or_create_improvement=kwargs.get("should_find_or_create_improvement", kind in {"CONCRETE_ERROR", "GENERAL_PROBLEM", "IMPROVEMENT_IDEA"}),
        proposed_improvement_title=kwargs.get("proposed_improvement_title", _improvement_title_for(title)),
        proposed_improvement_description=kwargs.get("proposed_improvement_description", f"Проанализировать feedback: {title}."),
        confidence=kwargs.get("confidence", 0.5),
        needs_clarification=kwargs.get("needs_clarification", False),
        clarification_question=kwargs.get("clarification_question", ""),
    )


def _is_correction(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in ("нет, это ", "поставь ", "это для проекта ", "исправь"))


def _is_neutral_reply(text: str) -> bool:
    return text in {"спасибо", "все правильно", "всё правильно", "отлично", "да", "понял", "поняла", "хорошо", "именно так", "ок", "окей"}


def _is_idea(text: str) -> bool:
    return any(marker in text for marker in ("надо, чтобы", "нужно ", "хорошо бы", "добавь возможность", "нужно показывать", "не создавай"))


def _is_general_problem(text: str) -> bool:
    return any(marker in text for marker in ("часто", "постоянно", "иногда", "снова", "опять")) and not _is_ambiguous(text)


def _is_concrete_error(text: str) -> bool:
    if ("товар" in text or "покуп" in text) and ("study" in text or "учеб" in text or "исслед" in text or "изуч" in text):
        return True
    if _is_general_problem(text) and "создала запись" in text and not any(marker in text for marker in ("неправильно", "ошибка", "не та база", "не в той базе", "неверная дата", "не тот проект", "дубликат", "фигн")):
        return False
    return any(marker in text for marker in ("неправильно", "ошибка", "не та база", "не в той базе", "неверная дата", "не тот проект", "дубликат", "фигн", "создала запись"))


def _is_ambiguous(text: str) -> bool:
    return text in {"опять неправильно", "снова неправильно", "неправильно", "ошибка", "не так"}


def _problem_title(text: str, *, recurring: bool) -> str:
    if ("товар" in text or "покуп" in text) and ("study" in text or "учеб" in text or "исслед" in text or "изуч" in text):
        return "Товар ошибочно классифицирован как Study"
    if "дат" in text:
        return "Дата неверно определяется или теряется"
    if "проект" in text:
        return "Проект неверно определяется"
    if "дубликат" in text or "дубли" in text:
        return "Создаются дубли записей"
    if "баз" in text:
        return "Запись создается не в той базе"
    return "Повторяющаяся проблема обратной связи" if recurring else "Ошибка по обратной связи пользователя"


def _idea_title(text: str) -> str:
    if "куда" in text and ("создан" in text or "записан" in text):
        return "Показывать, куда создана запись"
    if "проект" in text:
        return "Улучшить определение проекта по контексту"
    if "удален" in text or "удалением" in text:
        return "Спрашивать подтверждение перед удалением"
    if "дат" in text:
        return "Упростить изменение даты обычным сообщением"
    return "Добавить пользовательское улучшение"


def _concrete_description(title: str, *, has_context: bool) -> str:
    suffix = "Часть фактов восстановлена из interaction context." if has_context else "Конкретный interaction не определен."
    return f"{title}. {suffix} Неизвестные факты требуют анализа."


def _expected_from_text(text: str) -> str:
    if "товар" in text or "покуп" in text:
        return "Классификация Goods и создание записи в GOODS."
    if "дат" in text:
        return "Дата должна сохраняться согласно сообщению пользователя."
    if "проект" in text:
        return "Проект должен определяться из контекста или уточняться."
    if "куда" in text:
        return "Пользователь видит, куда создана запись."
    return ""


def _actual_from_text(text: str) -> str:
    if "study" in text or "учеб" in text or "исслед" in text:
        return "Сообщение обработано как Study."
    if "не та база" in text:
        return "Запись создана не в ожидаемой базе."
    if "дубликат" in text or "дубли" in text:
        return "Созданы дублирующиеся записи."
    return ""


def _actual_from_context(interaction: dict[str, Any]) -> str:
    created = interaction.get("created")
    classification = interaction.get("classification")
    if created or classification:
        return f"Контекст interaction: classification={bool(classification)}, created={bool(created)}."
    return ""


def _entity_from_text(text: str) -> str:
    if "товар" in text or "покуп" in text:
        return "Goods"
    if "задач" in text:
        return "Task"
    if "study" in text or "учеб" in text or "исслед" in text:
        return "Study"
    return "Unknown"


def _database_from_text(text: str) -> str:
    if "товар" in text or "покуп" in text:
        return "BUY"
    if "задач" in text:
        return "TASKS"
    if "study" in text or "учеб" in text or "исслед" in text:
        return "Study / На изучение"
    return "Другое"


def _component_from_text(text: str) -> str:
    if any(marker in text for marker in ("товар", "study", "учеб", "задач", "класси")):
        return "Классификация"
    if "notion" in text or "баз" in text or "запис" in text:
        return "Notion"
    if "telegram" in text or "сообщ" in text:
        return "Telegram"
    return "Другое"


def _severity_from_text(text: str) -> str:
    if any(marker in text for marker in ("потер", "ничего создавать", "не создавай")):
        return "Высокая"
    if any(marker in text for marker in ("часто", "постоянно", "опять", "снова")):
        return "Средняя"
    return "Низкая"


def _issue_type(feedback: NormalizedFeedback) -> str:
    title = feedback.normalized_title.casefold()
    if "дубл" in title:
        return "Создан дубликат"
    if "дат" in title:
        return "Неверная дата"
    if "баз" in title:
        return "Неверная база"
    if "класси" in title or feedback.affected_entity_type in {"Goods", "Task", "Study"}:
        return "Неверная классификация"
    return "Другое"


def _improvement_title_for(title: str) -> str:
    if "Goods" in title or "товар" in title or ("Study" in title and "Товар" in title):
        return "Уточнить различение Goods и Study"
    if "Дата" in title or "дат" in title:
        return "Улучшить извлечение и сохранение даты"
    if "Проект" in title or "проект" in title:
        return "Улучшить определение проекта"
    if "дубли" in title or "дубл" in title:
        return "Предотвращать создание дублей"
    return f"Улучшить обработку feedback: {title}"[:120]


def _interaction_context_summary(interaction: dict[str, Any]) -> str:
    if not interaction:
        return "Не найден."
    return "; ".join(
        [
            f"interaction_id={interaction.get('interaction_id') or 'не указан'}",
            f"input_found={bool(interaction.get('input_text'))}",
            f"classification_found={bool(interaction.get('classification'))}",
            f"created_found={bool(interaction.get('created'))}",
        ]
    )


def _tokens(text: str) -> set[str]:
    return {part for part in re.findall(r"[\wЁёА-яA-Za-z]+", text.casefold()) if len(part) > 3}


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _short_signal(text: str) -> str:
    return " ".join(text.split())[:180]


def _fingerprint(*parts: str) -> str:
    import hashlib

    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
