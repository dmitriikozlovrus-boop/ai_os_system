from __future__ import annotations

import re
from typing import Any

from .models import BacklogPriorityRecommendation, ImprovementSummary, NormalizedFeedback


def looks_like_backlog_feedback(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    if not normalized:
        return False
    markers = (
        "неправильно",
        "ошибка",
        "снова",
        "опять",
        "часто",
        "постоянно",
        "нужно",
        "хорошо бы",
        "добавь возможность",
        "не создавай",
        "дубликат",
        "не та база",
        "неверная дата",
        "не тот проект",
        "фигн",
        "добавь в backlog",
        "зафиксируй как улучшение",
    )
    return any(marker in normalized for marker in markers)


def looks_like_backlog_browse_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    if normalized.startswith("покажи ") and any(marker in normalized for marker in ("приоритет", "улучшен", "notion", "отлож", "идеи")):
        return True
    return any(marker in normalized for marker in ("покажи backlog", "какие улучшения накопились", "покажи открытые улучшения", "что нужно доработать"))


def looks_like_backlog_open_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return bool(re.search(r"\b(покажи|открой|подробнее)\s+(?:улучшение\s+)?(?:\d+|первое|второе|третье|четвертое|пятое)", normalized) or normalized.startswith("открой улучшение про "))


def looks_like_backlog_management_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("измени приоритет", "поставь высокий приоритет", "поставь средний приоритет", "поставь низкий приоритет", "отложи это улучшение", "верни в идеи"))


def looks_like_backlog_ai_triage_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("разбери backlog", "что требует моего внимания", "покажи необработанные улучшения", "что готово к доработке", "какие записи похожи"))


def looks_like_backlog_triage_open_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("разбери первое", "разбери второе", "что неясно", "подготовь вопросы по улучшению"))


def looks_like_duplicate_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("покажи возможные дубли", "какие улучшения можно объединить"))


def looks_like_split_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("раздели улучшение", "предложи разделение", "split"))


def looks_like_implementation_candidates_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("что лучше доработать следующим", "выбери кандидатов на доработку", "покажи самые важные готовые улучшения"))


def looks_like_existing_technical_spec_selection(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(
        marker in normalized
        for marker in (
            "выбираю первое",
            "выбираю второе",
            "выбираю первое для доработки",
            "подготовь тз по этому improvement",
            "подготовь тз по этому улучшению",
            "подготовь техническое задание по второму",
            "начинаем доработку",
            "перейди к техническому анализу",
        )
    )


def looks_like_backlog_diagnostics_request(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return normalized in {"проверь систему обратной связи", "диагностика backlog", "проверь интеграции"}


def wants_separate_improvement(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("создай отдельное", "отдельное улучшение", "создай новый"))


def wants_backlog_create(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return any(marker in normalized for marker in ("создай улучшение", "добавь это в backlog", "добавь в backlog", "зафиксируй как улучшение"))


def backlog_filters(text: str) -> dict[str, str]:
    normalized = " ".join(text.strip().casefold().split())
    filters = {"priority": "", "status": "", "component": ""}
    if "высок" in normalized:
        filters["priority"] = "Высокий"
    elif "средн" in normalized:
        filters["priority"] = "Средний"
    elif "низк" in normalized:
        filters["priority"] = "Низкий"
    if "отлож" in normalized:
        filters["status"] = "Отложено"
    elif "в работе" in normalized:
        filters["status"] = "В работе"
    elif "идеи" in normalized:
        filters["status"] = "Идея"
    if "notion" in normalized:
        filters["component"] = "Notion"
    elif "telegram" in normalized:
        filters["component"] = "Telegram"
    return filters


def sort_backlog_items(items: list[ImprovementSummary]) -> list[ImprovementSummary]:
    status_rank = {"В работе": 0, "Идея": 1, "Отложено": 2}
    priority_rank = {"Высокий": 0, "Средний": 1, "Низкий": 2}
    return sorted(items, key=lambda item: (status_rank.get(item.status, 9), priority_rank.get(item.priority, 9), -len(item.related_issue_urls), item.title))


def backlog_index_from_text(text: str) -> int | None:
    normalized = " ".join(text.strip().casefold().split())
    words = {"первое": 0, "первый": 0, "второе": 1, "второй": 1, "третье": 2, "третий": 2, "четвертое": 3, "четвертый": 3, "пятое": 4, "пятый": 4}
    for word, index in words.items():
        if word in normalized:
            return index
    match = re.search(r"\b(\d{1,2})\b", normalized)
    return int(match.group(1)) - 1 if match else None


def priority_from_text(text: str) -> str:
    normalized = " ".join(text.strip().casefold().split())
    if "высок" in normalized:
        return "Высокий"
    if "средн" in normalized:
        return "Средний"
    if "низк" in normalized:
        return "Низкий"
    return ""


def status_from_text(text: str) -> str:
    normalized = " ".join(text.strip().casefold().split())
    if "отлож" in normalized:
        return "Отложено"
    if "верни в идеи" in normalized or "идею" in normalized:
        return "Идея"
    if "в работу" in normalized or "в работе" in normalized:
        return "В работе"
    return ""


def improvement_location(component: str) -> str:
    if component in {"Notion", "Telegram"}:
        return component
    if component == "Классификация":
        return "Правила Дирижёра"
    return "Другое"


def format_backlog_existing_offer(improvement: ImprovementSummary, recommendation: BacklogPriorityRecommendation) -> str:
    reasons = "\n".join(f"- {reason}" for reason in recommendation.reasons)
    return f"Похоже, эта обратная связь относится к существующему улучшению:\n\n{improvement.title}\n\nДобавить этот случай в него?\n\nРекомендуемый приоритет: {recommendation.recommended_priority}\nScore: {recommendation.score}\nПричины:\n{reasons}"


def format_semantic_match_options(options: list[ImprovementSummary], matches: list[Any]) -> str:
    lines = ["Возможные связанные улучшения:"]
    for index, option in enumerate(options[:3], start=1):
        match = next((item for item in matches if item.improvement_id == option.page_id), None)
        reasons = "; ".join((match.reasons if match else [])[:2]) or "похоже по смыслу"
        lines.extend(["", f"{index}. {option.title}", f"Score: {match.score if match else 0}", f"Почему: {reasons}"])
    lines.append("\nВыбери номер или напиши: создай отдельное улучшение.")
    return "\n".join(lines)


def format_split_proposal(proposal: Any) -> str:
    titles = "\n".join(f"{index}. {title}" for index, title in enumerate(proposal.suggested_titles, start=1))
    return "Текущий Improvement может объединять разные проблемы:\n\n" + titles + "\n\nПредлагается оставить первую проблему здесь и создать отдельный Improvement для второй.\nБез отдельного подтверждения ничего не меняю."


def format_backlog_new_offer(feedback: NormalizedFeedback, recommendation: BacklogPriorityRecommendation) -> str:
    reasons = "\n".join(f"- {reason}" for reason in recommendation.reasons)
    return f"Подготовила новое улучшение:\n\nНазвание:\n{feedback.proposed_improvement_title}\n\nПроблема:\n{feedback.proposed_improvement_description}\n\nПредлагаемое изменение:\n{feedback.expected_behavior or 'Проанализировать feedback и подготовить изменение.'}\n\nРекомендуемый приоритет: {recommendation.recommended_priority}\nПричины:\n{reasons}\n\nСоздать его в backlog?"


def format_backlog_list(items: list[ImprovementSummary]) -> str:
    if not items:
        return "Открытых улучшений по этим фильтрам не найдено."
    lines = ["Открытый backlog:"]
    for index, item in enumerate(items, start=1):
        lines.extend(["", f"{index}. {item.title}", f"Статус: {item.status or 'Не указан'}", f"Приоритет: {item.priority or 'Не указан'}", f"Связанных случаев: {len(item.related_issue_urls)}", "Последний случай: Не определено"])
    return "\n".join(lines)


def format_backlog_detail(improvement: ImprovementSummary, recommendation: BacklogPriorityRecommendation) -> str:
    reasons = "\n".join(f"- {reason}" for reason in recommendation.reasons)
    return f"{improvement.title}\n\nСтатус: {improvement.status or 'Не указан'}\nПриоритет: {improvement.priority or 'Не указан'}\n\nОписание проблемы:\n{improvement.description or 'Не указано'}\n\nКоличество связанных ошибок: {len(improvement.related_issue_urls)}\n\nОсновные проявления:\n- {improvement.suggested_change or 'Не указаны'}\n\nОжидаемое поведение:\n{improvement.suggested_change or 'Требует уточнения'}\n\nРекомендация по приоритету: {recommendation.recommended_priority} ({recommendation.score})\nПричины:\n{reasons}\n\nNotion URL:\n{improvement.url}"
