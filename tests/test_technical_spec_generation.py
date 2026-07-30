import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import ImprovementSummary, SystemIssueSummary, TechnicalChangeProposal
from conductor.service import ConductorService


class TechnicalSpecGenerationTest(unittest.TestCase):
    def _service(self, tmp, *, enabled=True):
        service = object.__new__(ConductorService)
        service.settings = Mock(openai_model="m", confidence_threshold=0.70, technical_spec_generation_enabled=enabled)
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.notion = Mock()
        service.notion.get_improvement.return_value = self._improvement()
        service.notion.get_system_issues_by_references.return_value = [self._issue()]
        service.notion.list_projects.return_value = []
        service.openai = Mock()
        service.openai.generate_technical_change_proposal.return_value = self._proposal()
        service.repository_context = Mock()
        service.repository_context.find_relevant_files.return_value = ["conductor/openai_client.py", "tests/test_models.py"]
        service.repository_context.read_candidate_files.return_value = {
            "conductor/openai_client.py": "class OpenAIClient: pass",
            "tests/test_models.py": "def test_goods(): pass",
        }
        service.telegram = Mock()
        service.telegram.send_message.return_value = {"result": {"message_id": 77}}
        return service

    def _improvement(self):
        return ImprovementSummary(
            page_id="99999999-9999-9999-9999-999999999999",
            url="https://www.notion.so/improvement-99999999999999999999999999999999",
            title="Уточнить классификацию товаров",
            status="Идея",
            improvement_type="Правило",
            change_location="Правила Дирижёра",
            related_issue_urls=["https://www.notion.so/issue-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
        )

    def _issue(self):
        return SystemIssueSummary(
            page_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            url="https://www.notion.so/issue-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            title="Покрышка попала в Study",
            issue_type="Неверная классификация",
            severity="Средняя",
            database="BUY",
            input_data="Купить покрышку",
            description="Фактический результат Study, ожидаемый Goods",
            solution="Исправить правило классификации",
            detected_date="2026-07-30",
        )

    def _proposal(self, *, candidate_files=None, regression_tests=None):
        return TechnicalChangeProposal(
            improvement_title="Уточнить классификацию товаров",
            problem_statement="Товары для покупки ошибочно классифицируются как Study.",
            evidence_summary="Есть подтвержденный System Issue.",
            desired_behavior="Покупки должны попадать в Goods.",
            current_behavior="Покупки попадают в Study.",
            likely_root_cause="Недостаточно явное правило классификации.",
            change_type="Правило",
            affected_components=["classification"],
            candidate_files=candidate_files or ["conductor/openai_client.py", "tests/test_models.py"],
            required_changes=["Уточнить правило Goods.", "Добавить regression tests."],
            regression_tests=regression_tests or ["Покрышка создает Goods.", "Исследовательский вопрос остается Study."],
            acceptance_criteria=["Preview не сохраняет ТЗ.", "Сохранение требует отдельного подтверждения."],
            out_of_scope=["Не запускать Codex автоматически.", "Не создавать PR автоматически."],
            risks=["Может потребоваться уточнение Notion schema."],
            open_questions=[],
            confidence=0.82,
        )

    def test_explicit_notion_url_generates_preview_and_state(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)

            result = service.process_text(
                "Сформируй ТЗ https://www.notion.so/improvement-99999999999999999999999999999999",
                chat_id=42,
            )

            feedback = service.interactions.get_feedback(42)
            self.assertEqual(result["notes"], ["technical spec preview"])
            self.assertEqual(feedback["state"], "awaiting_technical_spec_full_view")
            self.assertIn("Показать полное ТЗ", service.telegram.send_message.call_args.args[1])
            service.notion.save_improvement_technical_spec.assert_not_called()

    def test_feature_flag_false_does_not_call_notion_or_openai(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp, enabled=False)

            result = service.process_text("Сформируй ТЗ", chat_id=42)

            self.assertEqual(result["notes"], ["technical spec disabled"])
            service.notion.get_improvement.assert_not_called()
            service.openai.generate_technical_change_proposal.assert_not_called()

    def test_missing_context_does_not_use_global_latest(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.remember_improvement(43, {"improvement_url": "other-chat-url"})

            result = service.process_text("Сформируй ТЗ", chat_id=42)

            self.assertEqual(result["notes"], ["technical spec context missing"])
            self.assertIn("Не удалось определить Improvement", service.telegram.send_message.call_args.args[1])
            service.notion.get_improvement.assert_not_called()

    def test_reply_selects_improvement_context(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.remember_improvement(
                42,
                {"improvement_url": "https://www.notion.so/reply-99999999999999999999999999999999", "bot_message_ids": [55]},
            )

            result = service.process_text("Подготовь задачу для Кодекса", chat_id=42, reply_to_message_id=55)

            self.assertEqual(result["notes"], ["technical spec preview"])
            service.notion.get_improvement.assert_called_once_with("https://www.notion.so/reply-99999999999999999999999999999999")

    def test_latest_improvement_is_chat_scoped(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.remember_improvement(
                42,
                {"improvement_url": "https://www.notion.so/latest-99999999999999999999999999999999"},
            )

            service.process_text("Сформируй ТЗ", chat_id=42)

            service.notion.get_improvement.assert_called_once_with("https://www.notion.so/latest-99999999999999999999999999999999")

    def test_latest_improvement_takes_priority_over_explicit_url(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.remember_improvement(
                42,
                {"improvement_url": "https://www.notion.so/latest-99999999999999999999999999999999"},
            )

            service.process_text(
                "Сформируй ТЗ https://www.notion.so/explicit-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                chat_id=42,
            )

            service.notion.get_improvement.assert_called_once_with("https://www.notion.so/latest-99999999999999999999999999999999")

    def test_full_view_then_save_requires_separate_confirmation(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_technical_spec_full_view",
                    "improvement_page_id": "99999999-9999-9999-9999-999999999999",
                    "markdown": "# Задача Codex",
                },
            )

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["technical spec shown"])
            self.assertEqual(service.interactions.get_feedback(42)["state"], "awaiting_technical_spec_save_confirmation")
            self.assertIn("```markdown", service.telegram.send_message.call_args_list[-2].args[1])
            self.assertIn("Сохранить это ТЗ", service.telegram.send_message.call_args.args[1])
            service.notion.save_improvement_technical_spec.assert_not_called()

    def test_save_confirmation_updates_notion_and_clears_state(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_technical_spec_save_confirmation",
                    "improvement_page_id": "99999999-9999-9999-9999-999999999999",
                    "markdown": "# Задача Codex",
                },
            )

            result = service.process_text("Сохрани", chat_id=42)

            self.assertEqual(result["notes"], ["technical spec saved"])
            service.notion.save_improvement_technical_spec.assert_called_once()
            self.assertIsNone(service.interactions.get_feedback(42))

    def test_save_decline_clears_state_without_update(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_technical_spec_save_confirmation",
                    "improvement_page_id": "99999999-9999-9999-9999-999999999999",
                    "markdown": "# Задача Codex",
                },
            )

            result = service.process_text("Нет", chat_id=42)

            self.assertEqual(result["notes"], ["technical spec save declined"])
            service.notion.save_improvement_technical_spec.assert_not_called()
            self.assertIsNone(service.interactions.get_feedback(42))

    def test_openai_unavailable_does_not_change_improvement(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.openai.generate_technical_change_proposal.side_effect = RuntimeError("AI-анализ недоступен")

            result = service.process_text(
                "Сформируй ТЗ https://www.notion.so/improvement-99999999999999999999999999999999",
                chat_id=42,
            )

            self.assertEqual(result["notes"], ["technical spec ai unavailable"])
            self.assertIn("AI-анализ недоступен", service.telegram.send_message.call_args.args[1])
            service.notion.save_improvement_technical_spec.assert_not_called()

    def test_invalid_proposal_is_rejected(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.openai.generate_technical_change_proposal.return_value = self._proposal(regression_tests=["Только один тест"])

            result = service.process_text(
                "Сформируй ТЗ https://www.notion.so/improvement-99999999999999999999999999999999",
                chat_id=42,
            )

            self.assertEqual(result["notes"], ["technical spec validation failed"])
            self.assertIn("минимум два regression test", service.telegram.send_message.call_args.args[1])
            service.notion.save_improvement_technical_spec.assert_not_called()

    def test_notion_save_error_returns_clear_response_and_clears_state(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.save_improvement_technical_spec.side_effect = RuntimeError("notion down")
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_technical_spec_save_confirmation",
                    "improvement_page_id": "99999999-9999-9999-9999-999999999999",
                    "markdown": "# Задача Codex",
                },
            )

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["technical spec save failed"])
            self.assertIn("Не смогла сохранить ТЗ", service.telegram.send_message.call_args.args[1])
            self.assertIsNone(service.interactions.get_feedback(42))


if __name__ == "__main__":
    unittest.main()
