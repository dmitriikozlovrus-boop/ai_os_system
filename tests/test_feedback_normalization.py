import unittest

from conductor.feedback_backlog import build_feedback_system_issue, normalize_feedback, priority_recommendation


class FeedbackNormalizationTest(unittest.TestCase):
    def test_emotional_feedback_becomes_neutral_and_keeps_original(self):
        feedback = normalize_feedback("Она опять какую-то фигню сделала и записала товар в учебу")

        self.assertEqual(feedback.feedback_kind, "CONCRETE_ERROR")
        self.assertEqual(feedback.normalized_title, "Товар ошибочно классифицирован как Study")
        self.assertEqual(feedback.original_text, "Она опять какую-то фигню сделала и записала товар в учебу")
        self.assertNotIn("фигню", feedback.normalized_description.casefold())

    def test_unknown_facts_are_not_invented_in_system_issue(self):
        feedback = normalize_feedback("Ты часто теряешь даты")
        issue = build_feedback_system_issue(feedback, interaction=None, today="2026-07-30")

        self.assertEqual(feedback.feedback_kind, "GENERAL_PROBLEM")
        self.assertFalse(feedback.should_create_system_issue)
        self.assertEqual(issue.input_data, "Не определено: feedback без привязки к конкретному interaction.")
        self.assertEqual(issue.classification.probable_cause, "Требует анализа.")

    def test_clean_idea_does_not_require_system_issue(self):
        feedback = normalize_feedback("Нужно показывать, куда создана запись")

        self.assertEqual(feedback.feedback_kind, "IMPROVEMENT_IDEA")
        self.assertFalse(feedback.should_create_system_issue)
        self.assertTrue(feedback.should_find_or_create_improvement)

    def test_correction_is_kept_separate_from_backlog_normalization(self):
        feedback = normalize_feedback("Нет, это товар", interaction={"interaction_id": "abc"})

        self.assertEqual(feedback.feedback_kind, "CORRECTION")
        self.assertFalse(feedback.should_find_or_create_improvement)

    def test_ambiguous_feedback_without_context_requires_clarification(self):
        feedback = normalize_feedback("Опять неправильно")

        self.assertEqual(feedback.feedback_kind, "UNKNOWN")
        self.assertTrue(feedback.needs_clarification)
        self.assertIn("Reply", feedback.clarification_question)

    def test_priority_recommendation_does_not_change_real_priority(self):
        feedback = normalize_feedback("Она опять записала товар в учебу")
        recommendation = priority_recommendation(feedback=feedback, signal_count=4, explicit_request=True)

        self.assertEqual(recommendation.recommended_priority, "Высокий")
        self.assertGreaterEqual(recommendation.score, 70)


if __name__ == "__main__":
    unittest.main()
