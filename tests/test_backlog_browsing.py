import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from conductor.interactions import InteractionStore
from conductor.models import ImprovementSummary
from conductor.service import ConductorService


class BacklogBrowsingTest(unittest.TestCase):
    def _service(self, tmp):
        service = object.__new__(ConductorService)
        service.settings = Mock(feedback_backlog_enabled=True, technical_spec_generation_enabled=False, openai_model="m")
        service.interactions = InteractionStore(f"{tmp}/interactions.json")
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.notion = Mock()
        service.notion.list_projects.return_value = []
        service.telegram = Mock()
        service.openai = Mock()
        return service

    def _item(self, index, *, status="Идея", priority="Средний", relation_count=0, component="Правила Дирижёра"):
        return ImprovementSummary(
            page_id=f"{index:032d}",
            url=f"https://www.notion.so/improvement-{index:032d}",
            title=f"Улучшение {index}",
            status=status,
            improvement_type="Правило",
            change_location=component,
            related_issue_urls=[str(i) for i in range(relation_count)],
            priority=priority,
            description=f"Описание {index}",
            suggested_change=f"Изменение {index}",
        )

    def test_backlog_list_is_limited_to_ten_and_sorted(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.list_open_improvements.return_value = [
                self._item(1, status="Идея", priority="Средний", relation_count=1),
                self._item(2, status="В работе", priority="Низкий", relation_count=1),
                *[self._item(i, priority="Высокий") for i in range(3, 15)],
            ]

            result = service.process_text("Покажи backlog", chat_id=42)

            self.assertEqual(result["count"], 10)
            shown = service.interactions.get_backlog_list(42)["items"]
            self.assertEqual(len(shown), 10)
            self.assertEqual(shown[0]["status"], "В работе")

    def test_priority_status_and_component_filters_are_passed_to_notion(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.list_open_improvements.return_value = []

            service.process_text("Покажи только высокий приоритет по Notion", chat_id=42)

            service.notion.list_open_improvements.assert_called_once_with(limit=10, priority="Высокий", status="", component="Notion")

    def test_open_second_uses_last_list_for_current_chat(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            first = self._item(1)
            second = self._item(2)
            service.interactions.remember_backlog_list(42, [first.__dict__, second.__dict__])
            service.interactions.remember_backlog_list(43, [self._item(9).__dict__])
            service.notion.get_improvement.return_value = second

            result = service.process_text("Покажи второе", chat_id=42)

            self.assertEqual(result["notes"], ["backlog item opened"])
            service.notion.get_improvement.assert_called_once_with(second.url)
            self.assertNotIn("Technical Spec", service.telegram.send_message.call_args.args[1])

    def test_expired_list_state_is_not_used(self):
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "interactions.json")
            expired = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            with open(path, "w", encoding="utf-8") as file:
                json.dump({"_backlog_lists": {"42": {"items": [self._item(1).__dict__], "timestamp": expired}}}, file)
            service = self._service(tmp)

            result = service.process_text("Покажи первое", chat_id=42)

            self.assertEqual(result["notes"], ["backlog context missing"])

    def test_priority_change_requires_confirmation(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            item = self._item(1)
            service.interactions.remember_backlog_list(42, [item.__dict__])

            result = service.process_text("Поставь высокий приоритет 1", chat_id=42)

            self.assertEqual(result["notes"], ["backlog priority confirmation requested"])
            service.notion.update_improvement_priority.assert_not_called()
            service.process_text("Да", chat_id=42)
            service.notion.update_improvement_priority.assert_called_once()

    def test_status_change_requires_confirmation(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            item = self._item(1)
            service.interactions.remember_backlog_list(42, [item.__dict__])

            result = service.process_text("Отложи это улучшение 1", chat_id=42)

            self.assertEqual(result["notes"], ["backlog status confirmation requested"])
            service.notion.update_improvement_status.assert_not_called()
            service.process_text("Да", chat_id=42)
            service.notion.update_improvement_status.assert_called_once()

    def test_notion_list_error_is_not_false_success(self):
        with TemporaryDirectory() as tmp:
            service = self._service(tmp)
            service.notion.list_open_improvements.side_effect = RuntimeError("notion down")

            result = service.process_text("Покажи backlog", chat_id=42)

            self.assertEqual(result["notes"], ["backlog list failed"])
            self.assertIn("notion down", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
