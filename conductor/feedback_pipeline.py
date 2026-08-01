from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import NormalizedFeedback, SystemIssueRecord, SystemIssueSummary


REPEAT_SECTION_START = "<!-- CONDUCTOR_SYSTEM_ISSUE_REPEAT_START -->"
REPEAT_SECTION_END = "<!-- CONDUCTOR_SYSTEM_ISSUE_REPEAT_END -->"


@dataclass
class FeedbackContextSnapshot:
    interaction_id: str
    input_text: str
    classification: dict[str, Any] | None
    created: dict[str, Any] | None
    pending: list[Any]
    questions: list[Any]
    errors: list[Any]
    route_trace: list[str]
    request_id: str
    conversation_id: str


@dataclass
class DuplicateDecision:
    action: str
    matched_issue: SystemIssueSummary | None
    score: int
    reason: str


def recover_feedback_context(interaction: dict[str, Any] | None, *, route_trace: list[str] | None = None) -> FeedbackContextSnapshot:
    interaction = interaction or {}
    return FeedbackContextSnapshot(
        interaction_id=str(interaction.get("interaction_id") or "Unknown"),
        input_text=str(interaction.get("input_text") or ""),
        classification=interaction.get("classification") if isinstance(interaction.get("classification"), dict) else None,
        created=interaction.get("created") if isinstance(interaction.get("created"), dict) else None,
        pending=list(interaction.get("pending") or []),
        questions=list(interaction.get("questions") or []),
        errors=list(interaction.get("errors") or []),
        route_trace=route_trace or [],
        request_id=str(interaction.get("request_id") or interaction.get("interaction_id") or "Unknown"),
        conversation_id=str(interaction.get("conversation_id") or interaction.get("chat_id") or "Unknown"),
    )


def context_snapshot_text(snapshot: FeedbackContextSnapshot) -> str:
    return "; ".join(
        [
            f"interaction_id={snapshot.interaction_id}",
            f"request_id={snapshot.request_id}",
            f"conversation_id={snapshot.conversation_id}",
            f"input_found={bool(snapshot.input_text)}",
            f"classification_found={bool(snapshot.classification)}",
            f"created_found={bool(snapshot.created)}",
            f"pending_count={len(snapshot.pending)}",
            f"question_count={len(snapshot.questions)}",
            f"error_count={len(snapshot.errors)}",
            f"route_trace={' > '.join(snapshot.route_trace) if snapshot.route_trace else 'Unknown'}",
        ]
    )


def choose_system_issue_duplicate(
    issue: SystemIssueRecord,
    candidates: list[SystemIssueSummary],
    *,
    threshold: int = 78,
) -> DuplicateDecision:
    scored = [(_duplicate_score(issue, candidate), candidate) for candidate in candidates if candidate.url]
    scored = [item for item in scored if item[0] >= threshold]
    if not scored:
        return DuplicateDecision("CREATE_NEW", None, 0, "No sufficiently similar System Issue candidate.")
    score, candidate = max(scored, key=lambda item: item[0])
    return DuplicateDecision(
        "UPDATE_EXISTING",
        candidate,
        score,
        "Matched by issue type, database and overlapping title/context tokens.",
    )


def repeat_solution_text(existing: SystemIssueSummary, issue: SystemIssueRecord, *, feedback: NormalizedFeedback, today: str) -> str:
    base_solution = _strip_repeat_section(existing.solution).strip() or "Требуется анализ и исправление."
    previous = _parse_repeat_section(existing.solution)
    count = max(previous["count"], _count_existing_occurrences(existing.description)) + 1
    examples = [*previous["examples"], f"{today}: {feedback.original_text[:180]}"]
    examples = _dedupe(examples)[-10:]
    lines = [
        base_solution,
        "",
        REPEAT_SECTION_START,
        f"Repeat Count: {count}",
        f"Last Seen: {today}",
        f"Latest Fingerprint: {issue.fingerprint}",
        "Latest Expected Behavior: " + (issue.classification.expected_result or feedback.expected_behavior or "Unknown"),
        "Latest Probable Cause: " + (issue.classification.probable_cause or "Unknown"),
        "Recent Examples:",
        *[f"- {item}" for item in examples],
        REPEAT_SECTION_END,
    ]
    return "\n".join(lines)


def _duplicate_score(issue: SystemIssueRecord, candidate: SystemIssueSummary) -> int:
    score = 0
    if candidate.issue_type == issue.classification.issue_type:
        score += 30
    if candidate.database == issue.classification.database:
        score += 20
    new_text = " ".join(
        [
            issue.classification.title,
            issue.classification.actual_result,
            issue.classification.expected_result,
            issue.input_data,
            issue.description,
        ]
    )
    candidate_text = " ".join([candidate.title, candidate.input_data, candidate.description, candidate.solution])
    new_tokens = _tokens(new_text)
    candidate_tokens = _tokens(candidate_text)
    if new_tokens and candidate_tokens:
        overlap = len(new_tokens & candidate_tokens)
        union = len(new_tokens | candidate_tokens)
        score += int((overlap / union) * 50)
        if _tokens(issue.classification.title) & _tokens(candidate.title):
            score += 15
        if overlap >= 4:
            score += 10
    return min(score, 100)


def _tokens(text: str) -> set[str]:
    return {part for part in re.findall(r"[\wЁёА-яA-Za-z]+", text.casefold()) if len(part) > 3}


def _strip_repeat_section(text: str) -> str:
    if REPEAT_SECTION_START not in text or REPEAT_SECTION_END not in text:
        return text
    before, rest = text.split(REPEAT_SECTION_START, 1)
    _, after = rest.split(REPEAT_SECTION_END, 1)
    return (before + after).strip()


def _parse_repeat_section(text: str) -> dict[str, Any]:
    if REPEAT_SECTION_START not in text or REPEAT_SECTION_END not in text:
        return {"count": 0, "examples": []}
    section = text.split(REPEAT_SECTION_START, 1)[1].split(REPEAT_SECTION_END, 1)[0]
    count = 0
    examples: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("Repeat Count:"):
            try:
                count = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                count = 0
        elif stripped.startswith("- "):
            examples.append(stripped[2:].strip())
    return {"count": count, "examples": examples}


def _count_existing_occurrences(text: str) -> int:
    lowered = text.casefold()
    markers = ("исходный feedback:", "обратная связь пользователя:", "latest fingerprint:")
    return sum(1 for marker in markers if marker in lowered)


def _dedupe(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
