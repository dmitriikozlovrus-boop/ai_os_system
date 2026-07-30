import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import Classification, ImprovementSummary
from conductor.service import ConductorService


class BacklogTriageTest(unittest.TestCase):
    def _service(self, tmp, *, ai=True, spec=True):
        service = object.__new__(ConductorService)
        service.settings = Mock(
            feedback_backlog_enabled=True,
            backlog_ai_triage_enabled=ai,
            technical_spec_generation_enabled=spec,
            openai_model="m",
        )
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.notion = Mock()
        service.notion.list_projects.return_value = []
        service.telegram = Mock()
        service.openai = Mock()
        service.openai.classify.return_value = Classification(tasks=[], studies=[], goods=[], notes=[])
        return service

    def _item(self, index=1, **overrides):
        data = {
            "page_id": f"{index:032d}",
            "url": f"https://www.notion.so/improvement-{index:032d}",
            "title": "Уточнить различение Goods и Study",
            "status": "Идея",
            "improvement_type": "Правило",
            "change_location": "Правила Дирижёра",
            "related_issue_urls": ["issue"],
            "priority": "Высокий",
            "description": "Физический товар попадает в Study.",
            "suggested_change": "Должна создаваться запись Goods.",
        }
        data.update(overrides)
        return ImprovementSummary(**data)

    def test_feature_flag_false_returns_unavailable_message(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp, ai=False)

            result = service.process_text("Разбери backlog", chat_id=42)

            self.assertEqual(result["notes"], ["backlog ai triage disabled"])
            self.assertIn("AI-разбор backlog", service.telegram.send_message.call_args.args[1])

    def test_triage_list_is_chat_scoped(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.list_open_improvements.return_value = [self._item(1), self._item(2, title="Улучшить даты")]

            result = service.process_text("Разбери backlog", chat_id=42)

            self.assertEqual(result["notes"], ["backlog triage shown"])
            self.assertEqual(len(service.interactions.get_triage_list(42)["items"]), 2)
            self.assertIsNone(service.interactions.get_triage_list(43))

    def test_open_first_uses_last_triage_list(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.remember_triage_list(42, [self._item(1, description="", suggested_change="").__dict__])

            result = service.process_text("Разбери первое", chat_id=42)

            self.assertEqual(result["notes"], ["backlog clarification requested"])
            self.assertEqual(service.interactions.get_feedback(42)["state"], "awaiting_backlog_clarification_answer")

    def test_clarification_answer_updates_existing_improvement_only(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {"state": "awaiting_backlog_clarification_answer", "improvement": self._item(1).__dict__},
            )

            result = service.process_text("Сейчас товар попадает в Study, должен попадать в Goods", chat_id=42)

            self.assertEqual(result["notes"], ["backlog clarification saved"])
            service.notion.create_improvement.assert_not_called()
            service.notion.create_system_issue.assert_not_called()
            service.notion.update_improvement_feedback_summary.assert_called_once()

    def test_implementation_candidates_do_not_create_technical_spec(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.list_open_improvements.return_value = [self._item(1)]

            result = service.process_text("Что лучше доработать следующим?", chat_id=42)

            self.assertEqual(result["notes"], ["implementation candidates shown"])
            service.notion.save_improvement_technical_spec.assert_not_called()

    def test_explicit_selection_hands_off_to_existing_technical_spec_flow(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.remember_triage_list(42, [self._item(1).__dict__])
            service._handle_technical_spec_request = Mock(return_value={"notes": ["technical spec preview"]})

            result = service.process_text("Выбираю первое", chat_id=42)

            self.assertEqual(result["notes"], ["technical spec preview"])
            service._handle_technical_spec_request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
