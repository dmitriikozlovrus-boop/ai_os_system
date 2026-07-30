import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.backlog_triage import normalize_with_ai, validate_feedback_enrichment
from conductor.feedback_backlog import normalize_feedback
from conductor.interactions import InteractionStore
from conductor.models import Classification, FeedbackEnrichment
from conductor.service import ConductorService


class FeedbackAIEnrichmentTest(unittest.TestCase):
    def _enrichment(self, **overrides):
        data = {
            "feedback_kind": "CONCRETE_ERROR",
            "normalized_title": "Дата неверно определена",
            "normalized_description": "Пользователь указал ошибку даты.",
            "actual_behavior": "Дата сохранена неверно.",
            "expected_behavior": "Дата должна соответствовать сообщению пользователя.",
            "affected_entity_type": "Task",
            "affected_database": "TASKS",
            "affected_component": "Классификация",
            "severity": "Средняя",
            "is_recurring_statement": False,
            "should_create_system_issue": True,
            "should_find_or_create_improvement": True,
            "proposed_improvement_title": "Улучшить извлечение даты",
            "proposed_improvement_description": "Уточнить правила даты.",
            "confidence": 0.8,
            "inferred_fields": ["actual_behavior"],
            "evidence": ["пользователь написал неверная дата"],
            "needs_clarification": False,
            "clarification_question": "",
        }
        data.update(overrides)
        return FeedbackEnrichment(**data)

    def test_ai_enrichment_success_preserves_original_text(self):
        openai = Mock()
        openai.enrich_feedback.return_value = self._enrichment()

        result = normalize_with_ai(openai=openai, raw_text="Здесь неверная дата", interaction={"chat_id": 42}, enabled=True)

        self.assertEqual(result.original_text, "Здесь неверная дата")
        self.assertEqual(result.normalized_title, "Дата неверно определена")
        openai.enrich_feedback.assert_called_once()

    def test_ai_cannot_add_unsupported_database(self):
        deterministic = normalize_feedback("Здесь неверная дата")
        error = validate_feedback_enrichment(self._enrichment(affected_database="UNKNOWN_DB"), deterministic, "Здесь неверная дата", None)

        self.assertEqual(error, "unsupported_database")

    def test_ai_invalid_output_falls_back(self):
        openai = Mock()
        openai.enrich_feedback.return_value = self._enrichment(affected_database="UNKNOWN_DB")

        result = normalize_with_ai(openai=openai, raw_text="Здесь неверная дата", interaction=None, enabled=True)

        self.assertEqual(result.normalized_title, normalize_feedback("Здесь неверная дата").normalized_title)

    def test_ai_failure_falls_back(self):
        openai = Mock()
        openai.enrich_feedback.side_effect = RuntimeError("openai down")

        result = normalize_with_ai(openai=openai, raw_text="Ты часто теряешь даты", interaction=None, enabled=True)

        self.assertEqual(result.feedback_kind, "GENERAL_PROBLEM")

    def test_other_chat_context_is_not_used_for_ai(self):
        with TemporaryDirectory() as tmp:
            service = object.__new__(ConductorService)
            service.settings = Mock(feedback_backlog_enabled=True, backlog_ai_triage_enabled=True, technical_spec_generation_enabled=False, openai_model="m")
            service.interactions = InteractionStore(f"{tmp}/interactions.json")
            other = service.interactions.create(99, text="Другой чат", telegram_message_id=99, model="m")
            service.interactions.update(other, status="completed")
            service.pending = Mock()
            service.pending.pop_oldest_for_chat.return_value = None
            service.recent = Mock()
            service.notion = Mock()
            service.notion.list_open_improvements.return_value = []
            service.notion.create_system_issue.return_value = "issue-url"
            service.notion.list_projects.return_value = []
            service.telegram = Mock()
            service.openai = Mock()
            service.openai.enrich_feedback.side_effect = RuntimeError("fallback")
            service.openai.classify.return_value = Classification(tasks=[], studies=[], goods=[], notes=[])

            service.process_text("Ты часто теряешь даты", chat_id=42)

            kwargs = service.openai.enrich_feedback.call_args.kwargs
            self.assertEqual(kwargs["interaction"], {})

    def test_reply_thanks_does_not_create_concrete_error(self):
        feedback = normalize_feedback("Спасибо", interaction={"interaction_id": "abc"})

        self.assertEqual(feedback.feedback_kind, "NOT_FEEDBACK")
        self.assertFalse(feedback.should_create_system_issue)

    def test_reply_error_uses_interaction(self):
        feedback = normalize_feedback("Здесь неверная дата", interaction={"interaction_id": "abc", "created": {"tasks": ["url"]}})

        self.assertEqual(feedback.feedback_kind, "CONCRETE_ERROR")
        self.assertTrue(feedback.should_create_system_issue)


if __name__ == "__main__":
    unittest.main()
