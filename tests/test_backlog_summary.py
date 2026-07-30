import unittest
from unittest.mock import patch

from conductor.feedback_backlog import feedback_summary_markdown
from conductor.notion_client import NotionClient


class BacklogSummaryTest(unittest.TestCase):
    def _block(self, block_id, block_type, text):
        return {
            "id": block_id,
            "type": block_type,
            block_type: {
                "rich_text": [
                    {
                        "plain_text": text,
                        "text": {"content": text},
                    }
                ]
            },
        }

    def test_summary_markdown_keeps_only_twenty_recent_signals(self):
        signals = [{"date": "2026-07-30", "title": f"T{i}", "original": f"signal {i}", "kind": "GENERAL_PROBLEM"} for i in range(25)]

        markdown = feedback_summary_markdown(signals=signals, related_issue_count=2, today="2026-07-30")

        self.assertEqual(markdown.count("signal "), 20)
        self.assertIn("Количество связанных случаев: 2", markdown)

    def test_start_and_end_replace_only_managed_section(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        children = {
            "results": [
                self._block("before", "paragraph", "До"),
                self._block("heading", "heading_2", "Сводка обратной связи"),
                self._block("start", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_START -->"),
                self._block("body", "paragraph", "old"),
                self._block("end", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_END -->"),
                self._block("after", "paragraph", "После"),
            ]
        }
        with patch("conductor.notion_client.request_json") as request_json:
            request_json.side_effect = [children, {}, {}, {}, {}, {"id": "append"}]
            client.update_improvement_feedback_summary("99999999999999999999999999999999", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_START -->\nnew\n<!-- CONDUCTOR_FEEDBACK_SUMMARY_END -->")

        archived = [call.args[1] for call in request_json.call_args_list if call.args[0] == "PATCH" and call.kwargs.get("payload") == {"archived": True}]
        self.assertEqual(
            archived,
            [
                "https://api.notion.com/v1/blocks/heading",
                "https://api.notion.com/v1/blocks/start",
                "https://api.notion.com/v1/blocks/body",
                "https://api.notion.com/v1/blocks/end",
            ],
        )

    def test_missing_end_marker_does_not_append_or_archive(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        children = {"results": [self._block("start", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_START -->")]}

        with patch("conductor.notion_client.request_json") as request_json:
            request_json.return_value = children
            with self.assertRaisesRegex(RuntimeError, "end marker is missing"):
                client.update_improvement_feedback_summary("99999999999999999999999999999999", "new")

        self.assertEqual(request_json.call_count, 1)

    def test_conflicting_markers_are_controlled_error(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        children = {
            "results": [
                self._block("start1", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_START -->"),
                self._block("start2", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_START -->"),
                self._block("end", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_END -->"),
            ]
        }

        with patch("conductor.notion_client.request_json") as request_json:
            request_json.return_value = children
            with self.assertRaisesRegex(RuntimeError, "Conflicting"):
                client.update_improvement_feedback_summary("99999999999999999999999999999999", "new")

    def test_pagination_after_one_hundred_blocks_is_supported(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        first_page = {"results": [self._block(f"b{i}", "paragraph", "x") for i in range(100)], "has_more": True, "next_cursor": "cursor"}
        second_page = {
            "results": [
                self._block("heading", "heading_2", "Сводка обратной связи"),
                self._block("start", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_START -->"),
                self._block("end", "paragraph", "<!-- CONDUCTOR_FEEDBACK_SUMMARY_END -->"),
            ],
            "has_more": False,
        }

        with patch("conductor.notion_client.request_json") as request_json:
            request_json.side_effect = [first_page, second_page, {}, {}, {}, {"id": "append"}]
            client.update_improvement_feedback_summary("99999999999999999999999999999999", "new")

        urls = [call.args[1] for call in request_json.call_args_list]
        self.assertIn("start_cursor=cursor", urls[1])

    def test_start_absent_appends_new_section(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        children = {"results": [self._block("before", "paragraph", "До")]}

        with patch("conductor.notion_client.request_json") as request_json:
            request_json.side_effect = [children, {"id": "append"}]
            client.update_improvement_feedback_summary("99999999999999999999999999999999", "new")

        self.assertEqual(request_json.call_args.args[0], "PATCH")
        payload = request_json.call_args.kwargs["payload"]
        self.assertEqual(payload["children"][0]["type"], "heading_2")


if __name__ == "__main__":
    unittest.main()
