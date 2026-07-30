import unittest
from tempfile import TemporaryDirectory

from conductor.backlog_context import resolve_improvement_context
from conductor.interactions import InteractionStore


class BacklogContextResolverTest(unittest.TestCase):
    def test_active_state_has_priority(self):
        with TemporaryDirectory() as tmp:
            store = InteractionStore(f"{tmp}/i.json")
            store.remember_triage_list(1, [{"page_id": "triage", "url": "u"}])
            context = resolve_improvement_context(interactions=store, text="первое", chat_id=1, active_state={"state": "s", "improvement": {"page_id": "active", "url": "u"}})
            self.assertEqual(context.source, "ACTIVE_STATE")
            self.assertEqual(context.improvement_id, "active")

    def test_reply_has_priority_over_number(self):
        with TemporaryDirectory() as tmp:
            store = InteractionStore(f"{tmp}/i.json")
            store.remember_improvement(1, {"page_id": "reply", "url": "u", "bot_message_ids": [10]})
            store.remember_triage_list(1, [{"page_id": "triage", "url": "u"}])
            context = resolve_improvement_context(interactions=store, text="первое", chat_id=1, reply_to_message_id=10)
            self.assertEqual(context.source, "REPLY")

    def test_current_chat_list_only(self):
        with TemporaryDirectory() as tmp:
            store = InteractionStore(f"{tmp}/i.json")
            store.remember_triage_list(2, [{"page_id": "other", "url": "u"}])
            with self.assertRaises(RuntimeError):
                resolve_improvement_context(interactions=store, text="первое", chat_id=1)

    def test_explicit_notion_url(self):
        with TemporaryDirectory() as tmp:
            store = InteractionStore(f"{tmp}/i.json")
            context = resolve_improvement_context(interactions=store, text="Подготовь ТЗ https://www.notion.so/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", chat_id=1)
            self.assertEqual(context.source, "EXPLICIT_NOTION_URL")
            self.assertEqual(context.improvement_id, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    def test_latest_requires_allow_latest(self):
        with TemporaryDirectory() as tmp:
            store = InteractionStore(f"{tmp}/i.json")
            store.remember_improvement(1, {"page_id": "latest", "url": "u"})
            with self.assertRaises(RuntimeError):
                resolve_improvement_context(interactions=store, text="это улучшение", chat_id=1)
            self.assertEqual(resolve_improvement_context(interactions=store, text="это улучшение", chat_id=1, allow_latest=True).source, "LATEST_IN_CURRENT_CHAT")


if __name__ == "__main__":
    unittest.main()
