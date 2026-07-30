import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import Classification, TaskItem
from conductor.openai_client import OpenAIClient
from conductor.service import ConductorService


class ServiceFeedbackRoutingTest(unittest.TestCase):
    def _service(self, tmp):
        service = object.__new__(ConductorService)
        service.settings = Mock(openai_model="m", confidence_threshold=0.70)
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.notion = Mock()
        service.notion.list_projects.return_value = []
        service.notion.create_task.return_value = "task-url"
        service.notion.create_goods.return_value = "goods-url"
        service.notion.create_system_issue.return_value = "issue-url"
        service.telegram = Mock()
        service.openai = Mock()
        return service

    def test_pending_answer_keeps_priority_over_non_feedback_short_text(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.pending.pop_oldest_for_chat.return_value = (
                "pending-id",
                {
                    "payload": {
                        "type": "task",
                        "item": {
                            "title": "Позвонить",
                            "description": "Позвонить",
                            "desired_result": "Совершенный звонок",
                            "project": "Общее",
                            "area": "Прочее",
                            "due_date": None,
                            "effort_minutes": 15,
                            "priority": "P2",
                            "next_step": "Позвонить",
                            "confidence": 0.6,
                            "missing": ["due_date"],
                        },
                    },
                    "questions": ["Какой срок исполнения?"],
                },
            )

            result = service.process_text("Завтра", chat_id=42)

            self.assertEqual(result["tasks_created"], ["task-url"])
            service.openai.classify.assert_not_called()

    def test_feedback_issue_save_failure_is_explicit_and_not_recursive(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.openai = OpenAIClient("", "unused", "unused")
            interaction_id = service.interactions.create(42, text="Покрышка 26x2", telegram_message_id=1, model="m")
            service.interactions.update(interaction_id, status="completed")
            service.notion.create_system_issue.side_effect = RuntimeError("notion down")

            result = service.process_text("Нет, это товар", chat_id=42)

            self.assertEqual(result["notes"], ["feedback issue save failed"])
            self.assertEqual(service.notion.create_system_issue.call_count, 1)
            self.assertIn("Не смогла сохранить ошибку", service.telegram.send_message.call_args.args[1])

    def test_after_confirmation_reprocesses_and_updates_issue(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.openai = OpenAIClient("", "unused", "unused")
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_fix_confirmation",
                    "interaction": {"input_text": "Позвонить Марко завтра по проекту Общее, направление Прочее"},
                    "correction": "Это задача",
                    "issue_url": "https://www.notion.so/test-12345678123412341234123456789012",
                },
            )

            result = service.process_text("Да, исправь", chat_id=42)

            self.assertIn("task-url", result["tasks_created"])
            service.notion.update_system_issue.assert_called_once()

    def test_existing_task_flow_still_classifies(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.pending.pop_oldest_for_chat.return_value = None
            service.openai.classify.return_value = Classification(
                tasks=[
                    TaskItem(
                        title="Позвонить Марко",
                        description="Позвонить Марко",
                        desired_result="Совершенный звонок",
                        project="Общее",
                        area="Прочее",
                        due_date="2026-05-21",
                        effort_minutes=15,
                        priority="P2",
                        next_step="Позвонить",
                        confidence=0.9,
                        missing=[],
                    )
                ],
                studies=[],
            )

            result = service.process_text("Позвонить Марко", chat_id=42)

            self.assertEqual(result["tasks_created"], ["task-url"])


if __name__ == "__main__":
    unittest.main()
