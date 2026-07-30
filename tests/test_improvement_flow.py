import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import SystemIssueSummary
from conductor.openai_client import OpenAIClient
from conductor.service import ConductorService


class ImprovementFlowTest(unittest.TestCase):
    def _service(self, tmp):
        service = object.__new__(ConductorService)
        service.settings = Mock(openai_model="m", confidence_threshold=0.70, system_improvements_enabled=True)
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.openai = OpenAIClient("", "unused", "unused")
        service.notion = Mock()
        service.notion.create_system_issue.return_value = "https://www.notion.so/new-12345678123412341234123456789012"
        service.notion.find_open_improvements_for_issues.return_value = []
        service.notion.create_improvement.return_value = "https://www.notion.so/improvement-99999999999999999999999999999999"
        service.notion.create_goods.return_value = "goods-url"
        service.notion.list_projects.return_value = []
        service.telegram = Mock()
        return service

    def _completed_study_interaction(self, service):
        interaction_id = service.interactions.create(42, text="Покрышка 26x2", telegram_message_id=1, model="m")
        service.interactions.update(
            interaction_id,
            status="completed",
            classification={"tasks": [], "studies": [{"question": "Покрышка 26x2"}], "goods": []},
        )

    def _candidate(self, title, url):
        return SystemIssueSummary(
            page_id=url.rsplit("-", 1)[-1],
            url=url,
            title=title,
            issue_type="Неверная классификация",
            severity="Средняя",
            database="BUY",
            input_data=title,
            description="Фактический результат: Study\nОжидаемый результат: Goods",
            solution="Нужно было создать товар Goods",
            detected_date="2026-07-29",
        )

    def test_single_error_does_not_offer_improvement(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            self._completed_study_interaction(service)
            service.notion.list_recent_system_issues.return_value = []

            result = service.process_text("Нет, это товар", chat_id=42)
            feedback = service.interactions.get_feedback(42)

            self.assertEqual(result["notes"], ["feedback issue saved"])
            self.assertNotIn("next_improvement", feedback)
            service.notion.create_improvement.assert_not_called()

    def test_three_similar_errors_offer_improvement_after_fix_decline(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            self._completed_study_interaction(service)
            service.notion.list_recent_system_issues.return_value = [
                self._candidate("Камера велосипеда", "https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
                self._candidate("Велосипедный насос", "https://www.notion.so/b-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
            ]

            service.process_text("Нет, это товар", chat_id=42)
            result = service.process_text("Нет", chat_id=42)
            feedback = service.interactions.get_feedback(42)

            self.assertEqual(result["notes"], ["feedback fix declined"])
            self.assertEqual(feedback["state"], "awaiting_improvement_confirmation")
            self.assertIn("Похоже, эта ошибка повторяется", service.telegram.send_message.call_args.args[1])
            service.notion.create_improvement.assert_not_called()

    def test_confirmed_improvement_is_created_with_idea_status_and_relations(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_improvement_confirmation",
                    "related_issue_urls": [
                        "https://www.notion.so/new-12345678123412341234123456789012",
                        "https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ],
                    "analysis": {
                        "is_recurring": True,
                        "related_issue_urls": ["https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
                        "recurrence_group_title": "Уточнить классификацию товаров",
                        "similarity_reason": "Study -> Goods",
                        "confidence": 0.7,
                        "suggested_improvement_title": "Уточнить классификацию товаров",
                        "suggested_improvement_description": "Похожие ошибки классификации Goods и Study.",
                        "suggested_change": "Добавить правило и regression-тесты.",
                        "improvement_type": "Правило",
                        "change_location": "Правила Дирижёра",
                        "priority": "Средний",
                    },
                },
            )

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["improvement created"])
            improvement = service.notion.create_improvement.call_args.args[0]
            self.assertEqual(improvement.status, "Идея")
            self.assertEqual(len(service.notion.create_improvement.call_args.kwargs["related_issue_urls"]), 2)

    def test_existing_improvement_is_linked_instead_of_duplicated(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_existing_improvement_link_confirmation",
                    "related_issue_urls": ["https://www.notion.so/new-12345678123412341234123456789012"],
                    "existing_improvement": {
                        "page_id": "improvement-page-id",
                        "url": "https://www.notion.so/improvement-page-id",
                        "title": "Уточнить классификацию товаров",
                        "status": "Идея",
                    },
                    "analysis": {},
                },
            )

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["improvement linked"])
            service.notion.create_improvement.assert_not_called()
            service.notion.add_issues_to_improvement.assert_called_once()

    def test_link_existing_improvement_preserves_and_deduplicates_relations(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_existing_improvement_link_confirmation",
                    "related_issue_urls": [
                        "https://www.notion.so/new-12345678123412341234123456789012",
                        "https://www.notion.so/old-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ],
                    "existing_improvement": {
                        "page_id": "improvement-page-id",
                        "url": "https://www.notion.so/improvement-page-id",
                        "title": "Уточнить классификацию товаров",
                        "status": "Идея",
                        "related_issue_urls": [
                            "https://www.notion.so/old-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                            "https://www.notion.so/other-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        ],
                    },
                    "analysis": {},
                },
            )

            service.process_text("Да", chat_id=42)

            related = service.notion.add_issues_to_improvement.call_args.kwargs["related_issue_urls"]
            self.assertEqual(
                related,
                [
                    "https://www.notion.so/old-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "https://www.notion.so/other-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "https://www.notion.so/new-12345678123412341234123456789012",
                ],
            )

    def test_recurrence_lookup_failure_does_not_break_issue_capture(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            self._completed_study_interaction(service)
            service.notion.list_recent_system_issues.side_effect = RuntimeError("notion search down")

            result = service.process_text("Нет, это товар", chat_id=42)

            self.assertEqual(result["notes"], ["feedback issue saved"])
            self.assertEqual(service.notion.create_system_issue.call_count, 1)

    def test_yes_routes_to_correction_before_improvement(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_correction_confirmation",
                    "interaction": {"input_text": "Нужна покрышка 26x2"},
                    "correction": "Нет, это товар",
                    "issue_url": "https://www.notion.so/new-12345678123412341234123456789012",
                    "next_improvement": {
                        "mode": "create",
                        "system_issue_url": "https://www.notion.so/new-12345678123412341234123456789012",
                        "related_issue_urls": ["https://www.notion.so/new-12345678123412341234123456789012"],
                        "analysis": {
                            "is_recurring": True,
                            "related_issue_urls": [],
                            "recurrence_group_title": "Уточнить классификацию товаров",
                            "similarity_reason": "forced",
                            "confidence": 0.7,
                            "suggested_improvement_title": "Уточнить классификацию товаров",
                            "suggested_improvement_description": "Похожие ошибки.",
                            "suggested_change": "Добавить правило.",
                            "improvement_type": "Правило",
                            "change_location": "Правила Дирижёра",
                            "priority": "Средний",
                        },
                    },
                },
            )

            result = service.process_text("Да", chat_id=42)
            feedback = service.interactions.get_feedback(42)

            self.assertEqual(result["goods_created"], ["goods-url"])
            self.assertEqual(feedback["state"], "awaiting_improvement_confirmation")
            service.notion.create_improvement.assert_not_called()

    def test_feature_flag_false_skips_improvement_offer(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.settings.system_improvements_enabled = False
            self._completed_study_interaction(service)
            service.notion.list_recent_system_issues.return_value = [
                self._candidate("Камера велосипеда", "https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
                self._candidate("Велосипедный насос", "https://www.notion.so/b-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
            ]

            result = service.process_text("Нет, это товар", chat_id=42)
            feedback = service.interactions.get_feedback(42)

            self.assertEqual(result["notes"], ["feedback issue saved"])
            self.assertNotIn("next_improvement", feedback)
            service.notion.list_recent_system_issues.assert_not_called()

    def test_declining_improvement_clears_state(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_improvement_confirmation",
                    "related_issue_urls": ["https://www.notion.so/new-12345678123412341234123456789012"],
                    "analysis": {
                        "is_recurring": True,
                        "related_issue_urls": [],
                        "recurrence_group_title": "Уточнить классификацию товаров",
                        "similarity_reason": "forced",
                        "confidence": 0.7,
                        "suggested_improvement_title": "Уточнить классификацию товаров",
                        "suggested_improvement_description": "Похожие ошибки.",
                        "suggested_change": "Добавить правило.",
                        "improvement_type": "Правило",
                        "change_location": "Правила Дирижёра",
                        "priority": "Средний",
                    },
                },
            )

            result = service.process_text("Нет", chat_id=42)

            self.assertEqual(result["notes"], ["improvement declined"])
            self.assertIsNone(service.interactions.get_feedback(42))

    def test_create_improvement_failure_does_not_leave_eternal_state(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.create_improvement.side_effect = RuntimeError("notion down")
            service.interactions.update_feedback(
                42,
                {
                    "state": "awaiting_improvement_confirmation",
                    "related_issue_urls": ["https://www.notion.so/new-12345678123412341234123456789012"],
                    "analysis": {
                        "is_recurring": True,
                        "related_issue_urls": [],
                        "recurrence_group_title": "Уточнить классификацию товаров",
                        "similarity_reason": "forced",
                        "confidence": 0.7,
                        "suggested_improvement_title": "Уточнить классификацию товаров",
                        "suggested_improvement_description": "Похожие ошибки.",
                        "suggested_change": "Добавить правило.",
                        "improvement_type": "Правило",
                        "change_location": "Правила Дирижёра",
                        "priority": "Средний",
                    },
                },
            )

            result = service.process_text("Да", chat_id=42)

            self.assertEqual(result["notes"], ["improvement create failed"])
            self.assertIsNone(service.interactions.get_feedback(42))


if __name__ == "__main__":
    unittest.main()
