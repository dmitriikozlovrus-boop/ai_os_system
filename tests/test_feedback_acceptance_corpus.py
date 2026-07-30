import json
import unittest
from pathlib import Path

from conductor.feedback_backlog import normalize_feedback


class FeedbackAcceptanceCorpusTest(unittest.TestCase):
    def test_acceptance_corpus(self):
        cases = json.loads(Path("tests/fixtures/feedback_acceptance_cases.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 30)
        for case in cases:
            with self.subTest(text=case["text"]):
                feedback = normalize_feedback(case["text"], interaction=case.get("interaction"))
                self.assertEqual(feedback.feedback_kind, case["expected_kind"])
                self.assertEqual(feedback.should_create_system_issue, case["system_issue"])
                self.assertEqual(feedback.should_find_or_create_improvement, case["improvement"])
                self.assertEqual(feedback.needs_clarification, case["clarification"])


if __name__ == "__main__":
    unittest.main()
