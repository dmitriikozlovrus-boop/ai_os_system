from __future__ import annotations

from typing import Any

from .backlog_helpers import backlog_index_from_text
from .backlog_triage import resolved_context
from .models import ResolvedImprovementContext
from .notion_client import notion_page_id_from_reference


def resolve_improvement_context(
    *,
    interactions: Any,
    text: str,
    chat_id: int,
    reply_to_message_id: int | None = None,
    active_state: dict[str, Any] | None = None,
    allow_latest: bool = False,
) -> ResolvedImprovementContext:
    if active_state and (active_state.get("improvement") or active_state.get("improvement_url") or active_state.get("improvement_page_id")):
        item = active_state.get("improvement") or active_state
        return _context_from_item(item, source="ACTIVE_STATE", chat_id=chat_id, state_name=str(active_state.get("state") or ""), confidence=1.0)

    remembered = interactions.find_improvement_by_reply(chat_id, reply_to_message_id)
    if remembered:
        return _context_from_item(remembered, source="REPLY", chat_id=chat_id, confidence=0.95)

    index = backlog_index_from_text(text)
    triage = interactions.get_triage_list(chat_id)
    if triage and index is not None:
        items = triage.get("items") or []
        if 0 <= index < len(items):
            return _context_from_item(items[index], source="TRIAGE_LIST_NUMBER", chat_id=chat_id, confidence=0.90)

    backlog = interactions.get_backlog_list(chat_id)
    if backlog and index is not None:
        items = backlog.get("items") or []
        if 0 <= index < len(items):
            return _context_from_item(items[index], source="BACKLOG_LIST_NUMBER", chat_id=chat_id, confidence=0.85)

    notion_url = _extract_notion_url(text)
    if notion_url:
        return resolved_context(improvement_id=notion_page_id_from_reference(notion_url), improvement_url=notion_url, source="EXPLICIT_NOTION_URL", chat_id=chat_id, confidence=0.80)

    if allow_latest:
        latest = interactions.latest_improvement(chat_id)
        if latest:
            return _context_from_item(latest, source="LATEST_IN_CURRENT_CHAT", chat_id=chat_id, confidence=0.70)

    raise RuntimeError("Не удалось однозначно определить Improvement в текущем chat.")


def _context_from_item(item: dict[str, Any], *, source: str, chat_id: int, confidence: float, state_name: str = "") -> ResolvedImprovementContext:
    url = str(item.get("improvement_url") or item.get("url") or "")
    page_id = str(item.get("improvement_page_id") or item.get("page_id") or "")
    if not page_id and url:
        page_id = notion_page_id_from_reference(url)
    if not page_id and not url:
        raise RuntimeError("Improvement context is incomplete.")
    return resolved_context(improvement_id=page_id, improvement_url=url, source=source, chat_id=chat_id, state_name=state_name, confidence=confidence)


def _extract_notion_url(text: str) -> str:
    for token in text.split():
        if "notion.so/" in token:
            return token.strip(".,)")
    return ""
