import unittest

from conductor.notion_client import NotionClient


class ManagedSectionsTest(unittest.TestCase):
    def _client(self):
        return NotionClient("token", "", "", "")

    def test_conflicting_markers_fail_before_write(self):
        client = self._client()
        blocks = [
            {"id": "1", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "CONDUCTOR_FEEDBACK_SUMMARY_START"}]}},
            {"id": "2", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "CONDUCTOR_FEEDBACK_SUMMARY_START"}]}},
        ]
        with self.assertRaises(RuntimeError):
            client._replace_managed_section("page", blocks, start_marker="CONDUCTOR_FEEDBACK_SUMMARY_START", end_marker="CONDUCTOR_FEEDBACK_SUMMARY_END", children=[], heading="Сводка обратной связи")

    def test_missing_end_fails_before_write(self):
        client = self._client()
        blocks = [{"id": "1", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "CONDUCTOR_TECH_SPEC_START"}]}}]
        with self.assertRaises(RuntimeError):
            client._replace_managed_section("page", blocks, start_marker="CONDUCTOR_TECH_SPEC_START", end_marker="CONDUCTOR_TECH_SPEC_END", children=[], heading="Техническое задание для Codex")


if __name__ == "__main__":
    unittest.main()
