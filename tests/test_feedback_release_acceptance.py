import unittest
import sys
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from unittest.mock import patch

from conductor.feedback_backlog_smoke import main as smoke_main
from conductor.service import ConductorService


class FeedbackReleaseAcceptanceTest(unittest.TestCase):
    def test_feature_flags_disable_layers_without_breaking_base_flow(self):
        with TemporaryDirectory() as tmp:
            service = object.__new__(ConductorService)
            service.settings = Mock(openai_model="m", confidence_threshold=0.70, feedback_backlog_enabled=False, backlog_ai_triage_enabled=False, technical_spec_generation_enabled=False)
            service.interactions = Mock()
            service.interactions.get_feedback.return_value = None
            service.interactions.find_by_reply.return_value = None
            service.interactions.latest_for_chat.return_value = None
            service.pending = Mock()
            service.pending.pop_oldest_for_chat.return_value = None
            service.recent = Mock()
            service.notion = Mock()
            service.notion.list_projects.return_value = []
            service.openai = Mock()
            service.openai.classify.return_value.tasks = []
            service.openai.classify.return_value.studies = []
            service.openai.classify.return_value.goods = []
            service.openai.classify.return_value.notes = []
            service.telegram = Mock()
            result = service.process_text("Позвонить Марко", chat_id=42)
            self.assertEqual(result["errors"], [])

    def test_write_smoke_refuses_without_explicit_write_flags(self):
        with patch("conductor.feedback_backlog_smoke.get_settings") as get_settings:
            get_settings.return_value = Mock(
                backlog_production_dry_run=True,
                smoke_test_writes_enabled=False,
            )
            with patch.object(sys, "argv", ["feedback_backlog_smoke", "--write-smoke"]):
                result = smoke_main()
            self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
