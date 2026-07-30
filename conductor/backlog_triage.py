from __future__ import annotations

from dataclasses import replace
from typing import Any

from .feedback_backlog import choose_matching_improvement, normalize_feedback, score_improvement_match
from .models import (
    BacklogMergeProposal,
    BacklogReadiness,
    BacklogSplitProposal,
    FeedbackEnrichment,
    ImprovementMatchCandidate,
    ImprovementSummary,
    NormalizedFeedback,
)


FEEDBACK_KINDS = {"CONCRETE_ERROR", "GENERAL_PROBLEM", "IMPROVEMENT_IDEA", "CORRECTION", "NOT_FEEDBACK", "UNKNOWN"}
DATABASES = {"TASKS", "PROBLEMS", "Study / На изучение", "EVENTS", "IDEAS", "COMMUNICATIONS", "CONTACTS", "FILMS", "BOOKS", "BUY", "SUBSCRIPTIONS", "Другое"}
SEVERITIES = {"Высокая", "Средняя", "Низкая"}
RELATION_TYPES = {"SAME_PROBLEM", "RELATED_PROBLEM", "POSSIBLE_MATCH", "NOT_RELATED"}


def normalize_with_ai(
    *,
    openai: Any,
    raw_text: str,
    interaction: dict[str, Any] | None,
    enabled: bool,
) -> NormalizedFeedback:
    deterministic = normalize_feedback(raw_text, interaction=interaction)
    if not enabled or deterministic.feedback_kind in {"CORRECTION", "NOT_FEEDBACK"}:
        return deterministic
    try:
        print("FEEDBACK_AI_ENRICHMENT_STARTED state=start", flush=True)
        enrichment = openai.enrich_feedback(raw_text=raw_text, deterministic=deterministic, interaction=_safe_interaction_context(interaction))
        validation_error = validate_feedback_enrichment(enrichment, deterministic, raw_text, interaction)
        if validation_error:
            print(f"FEEDBACK_AI_ENRICHMENT_REJECTED state={validation_error}", flush=True)
            return deterministic
        print(f"FEEDBACK_AI_ENRICHED feedback_kind={enrichment.feedback_kind} confidence={enrichment.confidence:.2f}", flush=True)
        return apply_enrichment(deterministic, enrichment)
    except Exception as exc:  # noqa: BLE001 - fallback is required when AI is unavailable.
        print(f"FEEDBACK_AI_ENRICHMENT_REJECTED state=exception error={type(exc).__name__}", flush=True)
        return deterministic


def validate_feedback_enrichment(
    enrichment: FeedbackEnrichment,
    deterministic: NormalizedFeedback,
    raw_text: str,
    interaction: dict[str, Any] | None,
) -> str | None:
    if enrichment.feedback_kind not in FEEDBACK_KINDS:
        return "unsupported_kind"
    if not enrichment.normalized_title.strip():
        return "empty_title"
    if enrichment.affected_database not in DATABASES:
        return "unsupported_database"
    if enrichment.severity not in SEVERITIES:
        return "unsupported_severity"
    if not 0 <= enrichment.confidence <= 1:
        return "confidence_out_of_range"
    if enrichment.feedback_kind == "NOT_FEEDBACK" and (enrichment.should_create_system_issue or enrichment.should_find_or_create_improvement):
        return "not_feedback_has_actions"
    if enrichment.feedback_kind == "CORRECTION" and enrichment.should_find_or_create_improvement:
        return "correction_captured_by_backlog"
    if enrichment.expected_behavior and not enrichment.evidence and "expected_behavior" in enrichment.inferred_fields:
        return "expected_without_evidence"
    if interaction and enrichment.actual_behavior and "Контекст interaction" not in deterministic.actual_behavior and deterministic.actual_behavior:
        if _contradicts(enrichment.actual_behavior, deterministic.actual_behavior):
            return "actual_contradicts_interaction"
    return None


def apply_enrichment(deterministic: NormalizedFeedback, enrichment: FeedbackEnrichment) -> NormalizedFeedback:
    return replace(
        deterministic,
        feedback_kind=enrichment.feedback_kind,
        normalized_title=enrichment.normalized_title.strip(),
        normalized_description=enrichment.normalized_description.strip(),
        actual_behavior=enrichment.actual_behavior.strip(),
        expected_behavior=enrichment.expected_behavior.strip(),
        affected_entity_type=enrichment.affected_entity_type.strip() or deterministic.affected_entity_type,
        affected_database=enrichment.affected_database,
        affected_component=enrichment.affected_component.strip() or deterministic.affected_component,
        severity=enrichment.severity,
        is_recurring_statement=enrichment.is_recurring_statement,
        should_create_system_issue=enrichment.should_create_system_issue,
        should_find_or_create_improvement=enrichment.should_find_or_create_improvement,
        proposed_improvement_title=enrichment.proposed_improvement_title.strip() or deterministic.proposed_improvement_title,
        proposed_improvement_description=enrichment.proposed_improvement_description.strip() or deterministic.proposed_improvement_description,
        confidence=enrichment.confidence,
        needs_clarification=enrichment.needs_clarification,
        clarification_question=enrichment.clarification_question.strip(),
    )


def semantic_match_improvements(
    *,
    openai: Any,
    feedback: NormalizedFeedback,
    shortlist: list[ImprovementSummary],
    enabled: bool,
) -> list[ImprovementMatchCandidate]:
    shortlist = shortlist[:10]
    if not shortlist:
        return []
    print(f"IMPROVEMENT_SEMANTIC_MATCH_STARTED candidate_count={len(shortlist)}", flush=True)
    if enabled:
        try:
            candidates = openai.match_improvements(feedback=feedback, candidates=shortlist)
            valid = [candidate for candidate in candidates if _valid_match(candidate, shortlist)]
            if valid:
                print(f"IMPROVEMENT_SEMANTIC_MATCH_COMPLETED candidate_count={len(valid)}", flush=True)
                return sorted(valid, key=lambda item: item.score, reverse=True)
        except Exception as exc:  # noqa: BLE001
            print(f"IMPROVEMENT_SEMANTIC_MATCH_COMPLETED candidate_count=0 state=fallback error={type(exc).__name__}", flush=True)
    fallback = [_deterministic_candidate(item, feedback) for item in shortlist]
    result = sorted(fallback, key=lambda item: item.score, reverse=True)
    print(f"IMPROVEMENT_SEMANTIC_MATCH_COMPLETED candidate_count={len(result)} state=deterministic", flush=True)
    return result


def choose_semantic_action(matches: list[ImprovementMatchCandidate]) -> str:
    if not matches or matches[0].score < 60:
        return "new"
    if matches[0].relation_type == "SAME_PROBLEM" and matches[0].score >= 85:
        return "link"
    return "choose"


def calculate_readiness(improvement: ImprovementSummary, signals: list[dict[str, Any]] | None = None) -> BacklogReadiness:
    signals = signals or []
    score = 20
    reasons = []
    missing = []
    signal_count = max(len(signals), len(improvement.related_issue_urls))
    if signal_count >= 3:
        score += 25
        reasons.append("есть несколько связанных сигналов")
    elif signal_count:
        score += 12
        reasons.append("есть хотя бы один сигнал")
    else:
        missing.append("нужны дополнительные сигналы")
    text = " ".join([improvement.title, improvement.description, improvement.suggested_change, *(str(item.get("title") or "") for item in signals), *(str(item.get("expected") or "") for item in signals)]).casefold()
    if any(marker in text for marker in ("ошиб", "сейчас", "фактичес", "попадает", "теряется", "создается")):
        score += 20
        reasons.append("описано фактическое поведение")
    else:
        missing.append("что система делает сейчас")
    if any(marker in text for marker in ("долж", "ожида", "нужно", "goods", "показывать", "сохранять")):
        score += 20
        reasons.append("понятно ожидаемое поведение")
    else:
        missing.append("что система должна делать вместо этого")
    if len(improvement.related_issue_urls) >= 1:
        score += 15
        reasons.append("есть конкретные System Issues")
    if _has_conflict(signals):
        score -= 25
        missing.append("есть конфликтующие ожидания")
    score = max(0, min(score, 100))
    if missing:
        status = "NEEDS_CLARIFICATION" if score >= 40 else "NEEDS_SIGNALS"
    elif score >= 80:
        status = "READY_FOR_IMPLEMENTATION_SELECTION"
    elif score >= 60:
        status = "READY_FOR_REVIEW"
    else:
        status = "NEEDS_SIGNALS"
    print(f"BACKLOG_READINESS_CALCULATED improvement_id={improvement.page_id} state={status} confidence={score/100:.2f}", flush=True)
    return BacklogReadiness(status=status, score=score, reasons=reasons or ["требуется ручной разбор"], missing_information=missing)


def triage_backlog(items: list[ImprovementSummary], signal_lookup: Any) -> list[tuple[ImprovementSummary, BacklogReadiness]]:
    pairs = [(item, calculate_readiness(item, signal_lookup(item.page_id))) for item in items[:10]]
    return sorted(pairs, key=lambda pair: (-pair[1].score, pair[0].title))


def format_triage_preview(pairs: list[tuple[ImprovementSummary, BacklogReadiness]]) -> str:
    groups = [
        ("Готовы к выбору для доработки", {"READY_FOR_IMPLEMENTATION_SELECTION"}),
        ("Требуют уточнения", {"NEEDS_CLARIFICATION"}),
        ("Недостаточно данных", {"NEEDS_SIGNALS", "READY_FOR_REVIEW"}),
    ]
    lines: list[str] = []
    counter = 1
    for title, statuses in groups:
        group = [(item, readiness) for item, readiness in pairs if readiness.status in statuses]
        if not group:
            continue
        lines.extend([title, ""])
        for item, readiness in group:
            reason = readiness.reasons[0] if readiness.reasons else "требуется разбор"
            lines.extend(
                [
                    f"{counter}. {item.title}",
                    f"Сигналов: {max(len(item.related_issue_urls), 0)}",
                    f"Готовность: {readiness.score}/100",
                    f"Причина: {reason}",
                    "",
                ]
            )
            counter += 1
    return "\n".join(lines).strip() or "Backlog пуст или недоступен."


def clarification_questions(readiness: BacklogReadiness) -> list[str]:
    base = readiness.missing_information or ["что система делает сейчас", "что она должна делать вместо этого"]
    questions = []
    for item in base[:3]:
        if "сейчас" in item:
            questions.append("Что система делает сейчас?")
        elif "должна" in item or "вместо" in item:
            questions.append("Что она должна делать вместо этого?")
        elif "конфликт" in item:
            questions.append("Какое ожидаемое поведение считать правильным?")
        else:
            questions.append("Ошибка возникает всегда или только в отдельных случаях?")
    return questions[:3]


def duplicate_pairs(items: list[ImprovementSummary], *, limit: int = 20) -> list[tuple[ImprovementSummary, ImprovementSummary, int]]:
    items = items[:limit]
    pairs = []
    checked = 0
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            checked += 1
            if checked > 30:
                break
            score = _pair_score(left, right)
            if score >= 60:
                pairs.append((left, right, score))
        if checked > 30:
            break
    print(f"BACKLOG_DUPLICATES_ANALYZED candidate_count={len(items)} signal_count={len(pairs)}", flush=True)
    return sorted(pairs, key=lambda item: item[2], reverse=True)


def build_merge_proposal(primary: ImprovementSummary, secondary: ImprovementSummary) -> BacklogMergeProposal:
    relation_ids = []
    for page_id in [*primary.related_issue_urls, *secondary.related_issue_urls]:
        if page_id and page_id not in relation_ids:
            relation_ids.append(page_id)
    return BacklogMergeProposal(
        primary_improvement_id=primary.page_id,
        secondary_improvement_id=secondary.page_id,
        primary_title=primary.title,
        secondary_title=secondary.title,
        relation_ids_to_keep=relation_ids,
        reasons=["похожие названия и ожидаемое изменение", "relations будут объединены без удаления второго Improvement"],
    )


def build_split_proposal(improvement: ImprovementSummary, signals: list[dict[str, Any]]) -> BacklogSplitProposal | None:
    text = " ".join([improvement.title, improvement.description, *(str(item.get("title") or "") for item in signals)]).casefold()
    titles = []
    if "дат" in text:
        titles.append("Улучшить обработку дат")
    if "проект" in text:
        titles.append("Улучшить определение проекта")
    if len(titles) < 2:
        return None
    return BacklogSplitProposal(improvement.page_id, improvement.title, titles[:2], ["в одном Improvement видны разные ожидаемые изменения"])


def implementation_candidates(pairs: list[tuple[ImprovementSummary, BacklogReadiness]]) -> list[tuple[ImprovementSummary, BacklogReadiness]]:
    ready = [pair for pair in pairs if pair[1].status in {"READY_FOR_IMPLEMENTATION_SELECTION", "READY_FOR_REVIEW"}]
    return sorted(ready, key=lambda pair: (-pair[1].score, _priority_rank(pair[0].priority), -len(pair[0].related_issue_urls)))[:5]


def format_implementation_candidates(candidates: list[tuple[ImprovementSummary, BacklogReadiness]]) -> str:
    if not candidates:
        return "Готовых кандидатов на доработку не найдено."
    lines = ["Кандидаты:"]
    for index, (item, readiness) in enumerate(candidates, start=1):
        lines.extend(
            [
                "",
                f"{index}. {item.title}",
                f"Готовность: {readiness.score}/100",
                "Почему сейчас:",
                *[f"- {reason}" for reason in readiness.reasons[:3]],
                "Риски:",
                *[f"- {missing}" for missing in (readiness.missing_information[:2] or ["перед стартом нужно подтвердить выбор"])],
            ]
        )
    return "\n".join(lines)


def format_duplicate_pairs(pairs: list[tuple[ImprovementSummary, ImprovementSummary, int]]) -> str:
    if not pairs:
        return "Возможные дубли не найдены."
    lines = ["Возможные дубли:"]
    for index, (left, right, score) in enumerate(pairs[:5], start=1):
        level = "высокая" if score >= 85 else "средняя"
        lines.extend(["", f"{index}. «{left.title}»", f"   и «{right.title}»", f"Вероятность: {level}", "Общая проблема: похожее ожидаемое изменение."])
    return "\n".join(lines)


def _safe_interaction_context(interaction: dict[str, Any] | None) -> dict[str, Any]:
    if not interaction:
        return {}
    return {
        "interaction_id": interaction.get("interaction_id"),
        "input_text": interaction.get("input_text"),
        "classification": interaction.get("classification"),
        "created": interaction.get("created"),
        "questions": interaction.get("questions"),
    }


def _contradicts(left: str, right: str) -> bool:
    left_lower = left.casefold()
    right_lower = right.casefold()
    return ("goods" in left_lower and "study" in right_lower and "goods" not in right_lower) or ("study" in left_lower and "goods" in right_lower and "study" not in right_lower)


def _valid_match(candidate: ImprovementMatchCandidate, shortlist: list[ImprovementSummary]) -> bool:
    ids = {item.page_id for item in shortlist}
    return candidate.improvement_id in ids and 0 <= candidate.score <= 100 and candidate.relation_type in RELATION_TYPES


def _deterministic_candidate(item: ImprovementSummary, feedback: NormalizedFeedback) -> ImprovementMatchCandidate:
    score = score_improvement_match(item, feedback)
    relation = "SAME_PROBLEM" if score >= 85 else "POSSIBLE_MATCH" if score >= 60 else "NOT_RELATED"
    return ImprovementMatchCandidate(item.page_id, score, relation, ["deterministic shortlist score"], [])


def _has_conflict(signals: list[dict[str, Any]]) -> bool:
    expected = {str(item.get("expected") or "").casefold() for item in signals if item.get("expected")}
    return len(expected) > 1 and any("без даты" in item for item in expected) and any("спраш" in item for item in expected)


def _pair_score(left: ImprovementSummary, right: ImprovementSummary) -> int:
    left_tokens = set(left.title.casefold().split())
    right_tokens = set(right.title.casefold().split())
    overlap = len(left_tokens & right_tokens) * 20
    if left.change_location == right.change_location:
        overlap += 10
    if left.priority == right.priority:
        overlap += 5
    return min(overlap, 100)


def _priority_rank(priority: str) -> int:
    return {"Высокий": 0, "Средний": 1, "Низкий": 2}.get(priority, 9)
