import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.openai_client import OpenAIClient
from conductor.service import ConductorService


class FeedbackIdempotencyTest(unittest.TestCase):
    def test_repeated_feedback_does_not_create_second_system_issue(self):
        with TemporaryDirectory() as tmp:
            service = object.__new__(ConductorService)
            service.settings = Mock(openai_model="m", confidence_threshold=0.70, backlog_production_dry_run=False, system_improvements_enabled=False)
            service.interactions = InteractionStore(f"{tmp}/i.json")
            service.pending = Mock()
            service.pending.pop_oldest_for_chat.return_value = None
            service.recent = Mock()
            service.openai = OpenAIClient("", "unused", "unused")
            service.notion = Mock()
            service.notion.create_system_issue.return_value = "https://www.notion.so/test-12345678123412341234123456789012"
            service.telegram = Mock()
            interaction_id = service.interactions.create(42, text="Покрышка", telegram_message_id=1, model="m")
            service.interactions.update(interaction_id, status="completed")

            first = service.process_text("Нет, это товар", chat_id=42)
            second = service.process_text("Нет, это товар", chat_id=42)

            self.assertEqual(first["notes"], ["feedback issue saved"])
            self.assertEqual(service.notion.create_system_issue.call_count, 1)

    def test_duplicate_signal_is_not_stored_twice(self):
        with TemporaryDirectory() as tmp:
            store = InteractionStore(f"{tmp}/i.json")
            signal = {"original": "Ты часто теряешь даты", "timestamp": "2026-07-30T00:00:00+00:00"}
            self.assertTrue(store.remember_feedback_signal("imp", signal))
            self.assertFalse(store.remember_feedback_signal("imp", signal))
            self.assertEqual(len(store.feedback_signals("imp")), 1)


if __name__ == "__main__":
    unittest.main()
