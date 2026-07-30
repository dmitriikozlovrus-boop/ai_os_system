import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.service import ConductorService


class FeedbackStateRestartTest(unittest.TestCase):
    def test_state_survives_restart_without_auto_write(self):
        with TemporaryDirectory() as tmp:
            path = f"{tmp}/i.json"
            first = InteractionStore(path)
            first.update_feedback(42, {"state": "awaiting_new_improvement_confirmation", "normalized_feedback": {"feedback_kind": "IMPROVEMENT_IDEA"}})

            second = InteractionStore(path)
            self.assertEqual(second.get_feedback(42)["state"], "awaiting_new_improvement_confirmation")

    def test_pending_technical_spec_save_requires_user_after_restart(self):
        with TemporaryDirectory() as tmp:
            path = f"{tmp}/i.json"
            InteractionStore(path).update_feedback(42, {"state": "awaiting_technical_spec_save_confirmation", "improvement_page_id": "imp", "markdown": "x"})
            service = object.__new__(ConductorService)
            service.settings = Mock(backlog_production_dry_run=True)
            service.interactions = InteractionStore(path)
            service.telegram = Mock()
            service.notion = Mock()

            service.process_text("пинг", chat_id=42)
            service.notion.save_improvement_technical_spec.assert_not_called()


if __name__ == "__main__":
    unittest.main()
