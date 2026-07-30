import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import ImprovementSummary
from conductor.service import ConductorService


class BacklogTechnicalSpecHandoffTest(unittest.TestCase):
    def _service(self, tmp, item):
        service = object.__new__(ConductorService)
        service.settings = Mock(feedback_backlog_enabled=True, backlog_ai_triage_enabled=True, technical_spec_generation_enabled=True, backlog_production_dry_run=False, openai_model="m")
        service.interactions = InteractionStore(f"{tmp}/i.json")
        service.telegram = Mock()
        service.notion = Mock()
        service.notion.get_improvement.return_value = item
        service.notion.get_system_issues_by_references.return_value = []
        service.repository_context = Mock()
        service.repository_context.find_relevant_files.return_value = []
        service.repository_context.read_candidate_files.return_value = {}
        service.openai = Mock()
        return service

    def _item(self, edited="t1", related=None, description="Сейчас дата теряется.", suggested="Система должна сохранять дату."):
        return ImprovementSummary("imp", "https://notion.so/imp", "Даты теряются", "Идея", "Правило", "Правила Дирижёра", related or ["issue"], "Средний", description, suggested, edited)

    def test_ready_selection_creates_snapshot_and_confirmation(self):
        with TemporaryDirectory() as tmp:
            item = self._item()
            service = self._service(tmp, item)
            service.interactions.remember_triage_list(42, [item.__dict__])
            result = service.process_text("Выбираю первое для доработки", chat_id=42)
            state = service.interactions.get_feedback(42)
            self.assertEqual(result["notes"], ["technical analysis confirmation requested"])
            self.assertEqual(state["snapshot"]["improvement_id"], "imp")

    def test_stale_last_edited_blocks_generation(self):
        with TemporaryDirectory() as tmp:
            item = self._item("t1")
            service = self._service(tmp, item)
            service.interactions.update_feedback(42, {"state": "awaiting_backlog_technical_analysis_confirmation", "snapshot": {"improvement_id": "imp", "improvement_title": "Даты", "improvement_last_edited_time": "old", "related_issue_ids": ["issue"], "feedback_summary_hash": "x", "readiness_status": "READY_FOR_IMPLEMENTATION_SELECTION", "readiness_score": 90, "selected_at": "now", "chat_id": 42}, "improvement": item.__dict__})
            result = service.process_text("Да", chat_id=42)
            self.assertEqual(result["notes"], ["technical analysis snapshot stale"])
            service.openai.generate_technical_change_proposal.assert_not_called()

    def test_ready_confirmation_uses_existing_technical_spec_flow(self):
        with TemporaryDirectory() as tmp:
            item = self._item("")
            service = self._service(tmp, item)
            service.openai.generate_technical_change_proposal.side_effect = RuntimeError("AI-анализ недоступен")
            service.interactions.remember_triage_list(42, [item.__dict__])
            service.process_text("Выбираю первое", chat_id=42)
            result = service.process_text("Да", chat_id=42)
            self.assertEqual(result["notes"], ["technical spec ai unavailable"])


if __name__ == "__main__":
    unittest.main()
