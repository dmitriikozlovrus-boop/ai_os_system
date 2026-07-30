import unittest
from unittest.mock import Mock

from conductor.integration_validation import IMPROVEMENTS_SCHEMA, SYSTEM_ISSUES_SCHEMA, validate_feedback_backlog_schema
from conductor.models import FeedbackEnrichment, ImprovementMatchCandidate, TechnicalChangeProposal
from conductor.integration_validation import validate_openai_contracts


class IntegrationValidationTest(unittest.TestCase):
    def test_correct_schema_passes_and_reverse_relation_not_required(self):
        notion = Mock(system_issues_db="sys", improvements_db="imp")
        notion.retrieve_database.side_effect = [{"properties": {k: {"type": v} for k, v in SYSTEM_ISSUES_SCHEMA.items()}}, {"properties": {k: {"type": v} for k, v in IMPROVEMENTS_SCHEMA.items()}}]
        results = validate_feedback_backlog_schema(notion)
        self.assertTrue(all(item.valid for item in results))

    def test_missing_and_wrong_property_are_reported(self):
        notion = Mock(system_issues_db="sys", improvements_db="imp")
        notion.retrieve_database.side_effect = [{"properties": {}}, {"properties": {"Какие ошибки исправляет": {"type": "rich_text"}}}]
        results = validate_feedback_backlog_schema(notion)
        self.assertFalse(all(item.valid for item in results))
        self.assertTrue(any("Missing property" in "; ".join(item.errors) or "Несовместимое поле" in "; ".join(item.errors) for item in results))

    def test_openai_contracts_parse_synthetic_outputs(self):
        openai = Mock()
        openai.enrich_feedback.return_value = FeedbackEnrichment("GENERAL_PROBLEM", "t", "d", "", "", "Unknown", "Другое", "Другое", "Средняя", True, False, True, "p", "pd", 0.5, [], ["[SMOKE TEST]"], False, "")
        openai.match_improvements.return_value = [ImprovementMatchCandidate("00000000-0000-0000-0000-000000000001", 50, "NOT_RELATED", [], [])]
        openai.generate_technical_change_proposal.return_value = TechnicalChangeProposal("i", "p", "e", "d", "c", "h", "rule", [], [], ["r"], ["t"], ["a"], [], [], [], 0.5)
        self.assertTrue(all(item.valid for item in validate_openai_contracts(openai)))


if __name__ == "__main__":
    unittest.main()
