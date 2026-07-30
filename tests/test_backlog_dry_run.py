import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import NormalizedFeedback
from conductor.service import ConductorService


class BacklogDryRunTest(unittest.TestCase):
    def test_dry_run_blocks_improvement_create(self):
        with TemporaryDirectory() as tmp:
            service = object.__new__(ConductorService)
            service.settings = Mock(backlog_production_dry_run=True)
            service.interactions = InteractionStore(f"{tmp}/i.json")
            service.telegram = Mock()
            service.notion = Mock()
            feedback = NormalizedFeedback("IMPROVEMENT_IDEA", "t", "d", "raw", "", "expected", "", "Другое", "Другое", "Средняя", False, False, False, True, "title", "desc", 0.8, False, "")
            result = service._create_backlog_improvement(42, {"normalized_feedback": feedback.__dict__, "related_issue_urls": []})
            self.assertEqual(result["notes"], ["dry-run improvement create blocked"])
            service.notion.create_improvement.assert_not_called()

    def test_dry_run_blocks_technical_spec_save(self):
        with TemporaryDirectory() as tmp:
            service = object.__new__(ConductorService)
            service.settings = Mock(backlog_production_dry_run=True)
            service.interactions = InteractionStore(f"{tmp}/i.json")
            service.telegram = Mock()
            service.notion = Mock()
            service.interactions.update_feedback(42, {"state": "awaiting_technical_spec_save_confirmation", "improvement_page_id": "imp", "markdown": "x"})
            result = service.process_text("Да", chat_id=42)
            self.assertEqual(result["notes"], ["dry-run technical spec save blocked"])
            service.notion.save_improvement_technical_spec.assert_not_called()


if __name__ == "__main__":
    unittest.main()
