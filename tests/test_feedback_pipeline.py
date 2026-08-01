import unittest

from conductor.feedback_backlog import build_feedback_system_issue, normalize_feedback
from conductor.feedback_pipeline import (
    REPEAT_SECTION_START,
    choose_system_issue_duplicate,
    context_snapshot_text,
    recover_feedback_context,
    repeat_solution_text,
)
from conductor.models import SystemIssueSummary


class FeedbackPipelineTest(unittest.TestCase):
    def test_context_snapshot_preserves_unknowns_and_trace(self):
        snapshot = recover_feedback_context(
            {"interaction_id": "abc", "chat_id": 42, "input_text": "Создай задачу", "classification": {"tasks": []}},
            route_trace=["reply", "feedback"],
        )

        self.assertEqual(snapshot.request_id, "abc")
        self.assertEqual(snapshot.conversation_id, "42")
        self.assertIn("route_trace=reply > feedback", context_snapshot_text(snapshot))

    def test_duplicate_decision_updates_similar_system_issue(self):
        feedback = normalize_feedback("Снова путаешь товары и изучение")
        issue = build_feedback_system_issue(feedback, interaction=None, today="2026-08-01")
        candidate = SystemIssueSummary(
            page_id="issue-1",
            url="https://www.notion.so/issue-1",
            title="Неверная классификация: Товар ошибочно классифицирован как Study",
            issue_type=issue.classification.issue_type,
            severity="Средняя",
            database=issue.classification.database,
            input_data="Покрышка для велосипеда",
            description="Товар ошибочно классифицирован как Study",
            solution="Требуется анализ",
            detected_date="2026-07-30",
        )

        decision = choose_system_issue_duplicate(issue, [candidate])

        self.assertEqual(decision.action, "UPDATE_EXISTING")
        self.assertEqual(decision.matched_issue, candidate)
        self.assertGreaterEqual(decision.score, 78)

    def test_repeat_solution_keeps_managed_repeat_section(self):
        feedback = normalize_feedback("Снова путаешь товары и изучение")
        issue = build_feedback_system_issue(feedback, interaction=None, today="2026-08-01")
        existing = SystemIssueSummary(
            page_id="issue-1",
            url="https://www.notion.so/issue-1",
            title="Неверная классификация: Товар ошибочно классифицирован как Study",
            issue_type=issue.classification.issue_type,
            severity="Средняя",
            database=issue.classification.database,
            input_data="",
            description="",
            solution="Требуется анализ",
            detected_date="2026-07-30",
        )

        text = repeat_solution_text(existing, issue, feedback=feedback, today="2026-08-01")

        self.assertIn(REPEAT_SECTION_START, text)
        self.assertIn("Repeat Count: 1", text)
        self.assertIn("Last Seen: 2026-08-01", text)


if __name__ == "__main__":
    unittest.main()
