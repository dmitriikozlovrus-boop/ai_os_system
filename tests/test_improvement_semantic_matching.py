import unittest
from unittest.mock import Mock

from conductor.backlog_triage import choose_semantic_action, semantic_match_improvements
from conductor.feedback_backlog import normalize_feedback
from conductor.models import ImprovementMatchCandidate, ImprovementSummary


class ImprovementSemanticMatchingTest(unittest.TestCase):
    def _improvement(self, page_id, title, *, component="Правила Дирижёра", database_text=""):
        return ImprovementSummary(
            page_id=page_id,
            url=f"https://www.notion.so/{page_id.replace('-', '')}",
            title=title,
            status="Идея",
            improvement_type="Правило",
            change_location=component,
            related_issue_urls=[],
            priority="Средний",
            description=database_text,
            suggested_change="",
        )

    def test_shortlist_is_limited_to_ten(self):
        openai = Mock()
        openai.match_improvements.return_value = []
        items = [self._improvement(str(index), f"Improvement {index}") for index in range(20)]

        semantic_match_improvements(openai=openai, feedback=normalize_feedback("Ты часто теряешь даты"), shortlist=items, enabled=True)

        self.assertEqual(len(openai.match_improvements.call_args.kwargs["candidates"]), 10)

    def test_same_database_is_not_enough_for_same_problem(self):
        feedback = normalize_feedback("Ты часто теряешь даты")
        item = self._improvement("a", "Улучшить проект", database_text="TASKS")

        result = semantic_match_improvements(openai=Mock(), feedback=feedback, shortlist=[item], enabled=False)[0]

        self.assertNotEqual(result.relation_type, "SAME_PROBLEM")

    def test_same_component_is_not_enough_for_same_problem(self):
        feedback = normalize_feedback("Ты часто теряешь даты")
        item = self._improvement("a", "Улучшить проект", component="Классификация")

        result = semantic_match_improvements(openai=Mock(), feedback=feedback, shortlist=[item], enabled=False)[0]

        self.assertNotEqual(result.relation_type, "SAME_PROBLEM")

    def test_semantically_same_formulations_are_found(self):
        openai = Mock()
        openai.match_improvements.return_value = [
            ImprovementMatchCandidate("a", 90, "SAME_PROBLEM", ["одно ожидаемое изменение"], [])
        ]

        result = semantic_match_improvements(
            openai=openai,
            feedback=normalize_feedback("Она опять записала товар в учебу"),
            shortlist=[self._improvement("a", "Уточнить определение Goods")],
            enabled=True,
        )

        self.assertEqual(result[0].relation_type, "SAME_PROBLEM")
        self.assertEqual(choose_semantic_action(result), "link")

    def test_related_but_different_problem_requires_choice(self):
        matches = [ImprovementMatchCandidate("a", 72, "RELATED_PROBLEM", ["один компонент"], [])]

        self.assertEqual(choose_semantic_action(matches), "choose")

    def test_score_below_sixty_creates_new(self):
        matches = [ImprovementMatchCandidate("a", 50, "POSSIBLE_MATCH", ["слабое сходство"], [])]

        self.assertEqual(choose_semantic_action(matches), "new")

    def test_score_above_eighty_five_still_requires_confirmation(self):
        matches = [ImprovementMatchCandidate("a", 90, "SAME_PROBLEM", ["сильное сходство"], [])]

        self.assertEqual(choose_semantic_action(matches), "link")


if __name__ == "__main__":
    unittest.main()
