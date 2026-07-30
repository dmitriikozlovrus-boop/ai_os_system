import unittest

from conductor.models import SystemIssueClassification, SystemIssueRecord, SystemIssueSummary
from conductor.openai_client import OpenAIClient


class IssueRecurrenceFallbackTest(unittest.TestCase):
    def _issue(self, *, severity="Средняя"):
        return SystemIssueRecord(
            classification=SystemIssueClassification(
                issue_type="Неверная классификация",
                severity=severity,
                database="BUY",
                actual_result='classification={"tasks": 0, "studies": 1, "goods": 0}',
                expected_result="Нет, это товар",
                probable_cause="Требуется анализ",
                title="Покрышка 26x2",
                correction_intent="CHANGE_ENTITY_TYPE",
                correction_target_type="Goods",
            ),
            detection_method="Пользователь",
            status="Новая",
            input_data="Покрышка 26x2",
            description="Фактический результат: Study\nОжидаемый результат: Goods",
            solution="Требуется анализ",
            detected_date="2026-07-30",
            fingerprint="fp",
        )

    def _candidate(self, title, url, *, description="Фактический результат: Study\nОжидаемый результат: Goods"):
        return SystemIssueSummary(
            page_id=url.rsplit("-", 1)[-1],
            url=url,
            title=title,
            issue_type="Неверная классификация",
            severity="Средняя",
            database="BUY",
            input_data=title,
            description=description,
            solution="Нужно было создать товар Goods",
            detected_date="2026-07-29",
        )

    def test_three_similar_errors_form_proposal_without_openai(self):
        client = OpenAIClient("", "unused", "unused")
        analysis = client.analyze_issue_recurrence(
            issue=self._issue(),
            issue_url="https://www.notion.so/new-12345678123412341234123456789012",
            candidates=[
                self._candidate("Камера велосипеда", "https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
                self._candidate("Велосипедный насос", "https://www.notion.so/b-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
            ],
        )

        self.assertTrue(analysis.is_recurring)
        self.assertEqual(len(analysis.related_issue_urls), 2)
        self.assertEqual(analysis.improvement_type, "Правило")
        self.assertEqual(analysis.change_location, "Правила Дирижёра")

    def test_same_type_and_database_are_not_enough(self):
        client = OpenAIClient("", "unused", "unused")
        analysis = client.analyze_issue_recurrence(
            issue=self._issue(),
            issue_url="https://www.notion.so/new-12345678123412341234123456789012",
            candidates=[
                self._candidate(
                    "Неверная классификация встречи",
                    "https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    description="Фактический результат: встреча записана не туда",
                ),
                self._candidate(
                    "Неверная классификация книги",
                    "https://www.notion.so/b-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    description="Фактический результат: книга попала не в ту базу",
                ),
            ],
        )

        self.assertFalse(analysis.is_recurring)
        self.assertEqual(analysis.related_issue_urls, [])

    def test_one_previous_high_severity_error_can_form_proposal(self):
        client = OpenAIClient("", "unused", "unused")
        analysis = client.analyze_issue_recurrence(
            issue=self._issue(severity="Высокая"),
            issue_url="https://www.notion.so/new-12345678123412341234123456789012",
            candidates=[self._candidate("Камера велосипеда", "https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")],
        )

        self.assertTrue(analysis.is_recurring)
        self.assertEqual(analysis.priority, "Высокий")

    def test_explicit_systemic_request_can_force_proposal(self):
        client = OpenAIClient("", "unused", "unused")
        analysis = client.analyze_issue_recurrence(
            issue=self._issue(),
            issue_url="https://www.notion.so/new-12345678123412341234123456789012",
            candidates=[],
            force_improvement=True,
        )

        self.assertTrue(analysis.is_recurring)
        self.assertEqual(analysis.related_issue_urls, [])


if __name__ == "__main__":
    unittest.main()
