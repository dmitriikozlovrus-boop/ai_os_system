import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.backlog_triage import build_merge_proposal, build_split_proposal, duplicate_pairs
from conductor.interactions import InteractionStore
from conductor.models import ImprovementSummary
from conductor.service import ConductorService


class BacklogMergeTest(unittest.TestCase):
    def _item(self, page_id, title, relations=None):
        return ImprovementSummary(
            page_id=page_id,
            url=f"https://www.notion.so/{page_id.replace('-', '')}",
            title=title,
            status="Идея",
            improvement_type="Правило",
            change_location="Правила Дирижёра",
            related_issue_urls=relations or [],
            priority="Средний",
            description="Физические товары попадают в Study.",
            suggested_change="Должны попадать в Goods.",
        )

    def _service(self, tmp):
        service = object.__new__(ConductorService)
        service.settings = Mock(feedback_backlog_enabled=True, backlog_ai_triage_enabled=True, technical_spec_generation_enabled=False, openai_model="m")
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.notion = Mock()
        service.notion.list_projects.return_value = []
        service.telegram = Mock()
        service.openai = Mock()
        return service

    def test_duplicate_analysis_limits_candidates_and_pairs(self):
        items = [self._item(str(index), f"Уточнить Goods {index}") for index in range(25)]

        pairs = duplicate_pairs(items)

        self.assertLessEqual(len(pairs), 30)

    def test_merge_proposal_preserves_and_deduplicates_relations(self):
        proposal = build_merge_proposal(
            self._item("primary", "Уточнить Goods", ["a", "b"]),
            self._item("secondary", "Исправить Goods", ["b", "c"]),
        )

        self.assertEqual(proposal.relation_ids_to_keep, ["a", "b", "c"])

    def test_merge_does_not_delete_secondary_improvement(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            primary = self._item("primary", "Уточнить Goods", ["a"]).__dict__
            secondary = self._item("secondary", "Исправить Goods", ["b"]).__dict__
            proposal = build_merge_proposal(ImprovementSummary(**primary), ImprovementSummary(**secondary)).__dict__
            service.interactions.update_feedback(42, {"state": "awaiting_backlog_merge_confirmation", "proposal": proposal, "primary": primary, "secondary": secondary})

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["backlog merge confirmed"])
            service.notion.add_issues_to_improvement.assert_called_once()
            service.notion.update_improvement_status.assert_called_once_with("secondary", "Отложено")
            self.assertFalse(hasattr(service.notion, "delete_improvement") and service.notion.delete_improvement.called)

    def test_merge_failure_before_primary_update_changes_nothing(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.add_issues_to_improvement.side_effect = RuntimeError("notion down")
            primary = self._item("primary", "Уточнить Goods").__dict__
            secondary = self._item("secondary", "Исправить Goods").__dict__
            proposal = build_merge_proposal(ImprovementSummary(**primary), ImprovementSummary(**secondary)).__dict__
            service.interactions.update_feedback(42, {"state": "awaiting_backlog_merge_confirmation", "proposal": proposal, "primary": primary, "secondary": secondary})

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["backlog merge failed"])
            service.notion.update_improvement_status.assert_not_called()

    def test_partial_merge_reports_partial_status(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.update_improvement_status.side_effect = RuntimeError("status down")
            primary = self._item("primary", "Уточнить Goods").__dict__
            secondary = self._item("secondary", "Исправить Goods").__dict__
            proposal = build_merge_proposal(ImprovementSummary(**primary), ImprovementSummary(**secondary)).__dict__
            service.interactions.update_feedback(42, {"state": "awaiting_backlog_merge_confirmation", "proposal": proposal, "primary": primary, "secondary": secondary})

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["backlog merge partial"])

    def test_split_proposal_does_not_change_without_confirmation(self):
        proposal = build_split_proposal(
            self._item("imp", "Улучшить даты и проекты", []),
            [{"title": "Неверная дата"}, {"title": "Неверный проект"}],
        )

        self.assertIsNotNone(proposal)
        self.assertGreaterEqual(len(proposal.suggested_titles), 2)


if __name__ == "__main__":
    unittest.main()
