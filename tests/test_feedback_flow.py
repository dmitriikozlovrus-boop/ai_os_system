import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.openai_client import OpenAIClient
from conductor.service import ConductorService, _looks_like_feedback


class FeedbackFlowTest(unittest.TestCase):
    def _service(self, tmp):
        service = object.__new__(ConductorService)
        service.settings = Mock(openai_model="m", confidence_threshold=0.70)
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.openai = OpenAIClient("", "unused", "unused")
        service.notion = Mock()
        service.notion.create_system_issue.return_value = "https://www.notion.so/test-12345678123412341234123456789012"
        service.telegram = Mock()
        return service

    def test_natural_entity_feedback_is_captured_without_command(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            interaction_id = service.interactions.create(42, text="Покрышка 26x2", telegram_message_id=1, model="m")
            service.interactions.update(interaction_id, status="completed", classification={"tasks": [], "studies": [{"question": "Покрышка"}], "goods": []})

            result = service.process_text("Нет, это товар", chat_id=42)

            self.assertEqual(result["notes"], ["feedback issue saved"])
            service.openai.classify.assert_not_called() if isinstance(service.openai, Mock) else None
            issue = service.notion.create_system_issue.call_args.args[0]
            self.assertEqual(issue.classification.correction_intent, "CHANGE_ENTITY_TYPE")
            self.assertEqual(issue.classification.correction_target_type, "Goods")

    def test_reply_targets_replied_interaction_not_latest(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            old_id = service.interactions.create(42, text="Старая запись", telegram_message_id=10, model="m")
            service.interactions.update(old_id, status="completed")
            latest_id = service.interactions.create(42, text="Новая запись", telegram_message_id=20, model="m")
            service.interactions.update(latest_id, status="completed")

            service.process_text("Нет, это задача", chat_id=42, reply_to_message_id=10)

            issue = service.notion.create_system_issue.call_args.args[0]
            self.assertIn("Старая запись", issue.input_data)

    def test_feedback_without_context_is_not_lost(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)

            result = service.process_text("Нет, это товар", chat_id=42)

            self.assertEqual(result["notes"], ["feedback context requested"])
            self.assertIn("не смогла определить", service.telegram.send_message.call_args.args[1])

    def test_false_positive_phrases_are_not_feedback(self):
        for text in (
            "Ошибка Байеса",
            "Книга называется “Ошибка”",
            "Изучи ошибки классификации",
            "Купить книгу “Неправильно”",
            "Встреча не так важна",
        ):
            with self.subTest(text=text):
                self.assertFalse(_looks_like_feedback(text, has_context=True, is_reply=False))

    def test_field_and_cancel_intents(self):
        client = OpenAIClient("", "unused", "unused")
        field = client.classify_system_issue(original_text="Встреча", actual_context={}, command="", correction="Дата неверная, встреча завтра")
        cancel = client.classify_system_issue(original_text="Комментарий", actual_context={}, command="", correction="Ничего создавать не надо")

        self.assertEqual(field.correction_intent, "CHANGE_FIELDS")
        self.assertIn("date", field.corrected_fields)
        self.assertEqual(cancel.correction_intent, "NO_ACTION_EXPECTED")


if __name__ == "__main__":
    unittest.main()
