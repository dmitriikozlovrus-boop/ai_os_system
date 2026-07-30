import unittest

from conductor.backlog_triage import calculate_readiness, clarification_questions
from conductor.models import ImprovementSummary


class BacklogReadinessTest(unittest.TestCase):
    def _improvement(self, **overrides):
        data = {
            "page_id": "imp",
            "url": "url",
            "title": "Уточнить различение Goods и Study",
            "status": "Идея",
            "improvement_type": "Правило",
            "change_location": "Правила Дирижёра",
            "related_issue_urls": ["issue"],
            "priority": "Средний",
            "description": "Физический товар попадает в Study.",
            "suggested_change": "Должна создаваться запись Goods.",
        }
        data.update(overrides)
        return ImprovementSummary(**data)

    def test_readiness_requires_actual_and_expected_behavior(self):
        readiness = calculate_readiness(self._improvement(description="", suggested_change=""), [])

        self.assertIn(readiness.status, {"NEEDS_SIGNALS", "NEEDS_CLARIFICATION"})
        self.assertTrue(readiness.missing_information)

    def test_general_idea_can_be_ready_for_review_without_system_issue(self):
        readiness = calculate_readiness(
            self._improvement(related_issue_urls=[], title="Показывать куда создана запись", description="Сейчас пользователь не видит результат.", suggested_change="Нужно показывать базу."),
            [{"kind": "IMPROVEMENT_IDEA", "title": "Показывать куда создана запись", "expected": "Пользователь видит базу"}],
        )

        self.assertIn(readiness.status, {"READY_FOR_REVIEW", "READY_FOR_IMPLEMENTATION_SELECTION"})

    def test_conflicting_expectations_need_clarification(self):
        readiness = calculate_readiness(
            self._improvement(),
            [
                {"expected": "система должна спрашивать дату"},
                {"expected": "система должна сохранять без даты"},
            ],
        )

        self.assertIn("есть конфликтующие ожидания", readiness.missing_information)

    def test_questions_are_simple_and_limited_to_three(self):
        readiness = calculate_readiness(self._improvement(description="", suggested_change=""), [])

        questions = clarification_questions(readiness)

        self.assertLessEqual(len(questions), 3)
        self.assertTrue(all(question.endswith("?") for question in questions))


if __name__ == "__main__":
    unittest.main()
