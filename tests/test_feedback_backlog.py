import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import ImprovementSummary
from conductor.service import ConductorService


class FeedbackBacklogTest(unittest.TestCase):
    def _service(self, tmp, *, enabled=True):
        service = object.__new__(ConductorService)
        service.settings = Mock(
            openai_model="m",
            confidence_threshold=0.70,
            feedback_backlog_enabled=enabled,
            technical_spec_generation_enabled=False,
            system_improvements_enabled=True,
        )
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.notion = Mock()
        service.notion.create_system_issue.return_value = "https://www.notion.so/issue-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        service.notion.create_improvement.return_value = "https://www.notion.so/improvement-99999999999999999999999999999999"
        service.notion.list_open_improvements.return_value = []
        service.notion.list_projects.return_value = []
        service.telegram = Mock()
        service.openai = Mock()
        return service

    def _improvement(self, title="Уточнить различение Goods и Study"):
        return ImprovementSummary(
            page_id="99999999-9999-9999-9999-999999999999",
            url="https://www.notion.so/improvement-99999999999999999999999999999999",
            title=title,
            status="Идея",
            improvement_type="Правило",
            change_location="Правила Дирижёра",
            related_issue_urls=["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
            priority="Средний",
            description="Проблема Goods и Study в BUY.",
            suggested_change="Уточнить классификацию Goods.",
        )

    def test_general_problem_without_interaction_proposes_backlog_item(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)

            result = service.process_text("Ты часто теряешь даты", chat_id=42)

            self.assertEqual(result["notes"], ["feedback new improvement proposed"])
            service.notion.create_system_issue.assert_not_called()
            self.assertEqual(service.interactions.get_feedback(42)["state"], "awaiting_new_improvement_confirmation")

    def test_cancel_clears_feedback_state_without_reprocessing(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_feedback_clarification",
                    "command": "Нужно что-то улучшить",
                    "normalized_feedback": {},
                },
            )

            result = service.process_text("отмена", chat_id=42)

            self.assertEqual(result["notes"], ["feedback state cancelled"])
            self.assertIsNone(service.interactions.get_feedback(42))
            service.openai.classify.assert_not_called()
            service.notion.create_system_issue.assert_not_called()

    def test_clean_idea_can_be_added_without_system_issue_after_confirmation(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)

            service.process_text("Нужно показывать, куда создана запись", chat_id=42)
            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["backlog improvement created"])
            service.notion.create_system_issue.assert_not_called()
            service.notion.create_improvement.assert_called_once()
            service.notion.update_improvement_feedback_summary.assert_called_once()

    def test_explicit_add_to_backlog_creates_without_second_prompt(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)

            result = service.process_text("Добавь в backlog: нужно показывать, куда создана запись", chat_id=42)

            self.assertEqual(result["notes"], ["backlog improvement created"])
            service.notion.create_improvement.assert_called_once()

    def test_existing_improvement_is_proposed_instead_of_duplicate(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.list_open_improvements.return_value = [self._improvement()]

            result = service.process_text("Она опять записала товар в учебу", chat_id=42)

            self.assertEqual(result["notes"], ["feedback matched improvement"])
            self.assertEqual(service.interactions.get_feedback(42)["state"], "awaiting_existing_improvement_link_confirmation")
            service.notion.create_improvement.assert_not_called()

    def test_link_existing_preserves_relations_and_updates_summary(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.list_open_improvements.return_value = [self._improvement()]

            service.process_text("Она опять записала товар в учебу", chat_id=42)
            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["improvement linked"])
            related = service.notion.add_issues_to_improvement.call_args.kwargs["related_issue_urls"]
            self.assertEqual(len(related), len(set(related)))
            service.notion.update_improvement_feedback_summary.assert_called_once()

    def test_feature_flag_false_leaves_existing_feedback_flow(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp, enabled=False)
            interaction_id = service.interactions.create(42, text="Покрышка", telegram_message_id=10, model="m")
            service.interactions.update(interaction_id, status="completed")

            result = service.process_text("Неправильно", chat_id=42)

            self.assertEqual(result["notes"], ["feedback correction requested"])
            service.notion.list_open_improvements.assert_not_called()

    def test_duplicate_signal_is_not_stored_twice(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            feedback_state = {
                "page_id": "99999999-9999-9999-9999-999999999999",
                "url": "https://www.notion.so/improvement-99999999999999999999999999999999",
                "related_issue_urls": [],
            }
            from conductor.feedback_backlog import normalize_feedback

            feedback = normalize_feedback("Ты часто теряешь даты")
            service._update_backlog_summary_for_feedback(feedback_state, feedback)
            service._update_backlog_summary_for_feedback(feedback_state, feedback)

            self.assertEqual(len(service.interactions.feedback_signals("99999999-9999-9999-9999-999999999999")), 1)


if __name__ == "__main__":
    unittest.main()
