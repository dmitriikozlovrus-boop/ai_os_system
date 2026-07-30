import unittest
from unittest.mock import patch

from conductor.models import SystemIssueClassification, SystemIssueRecord
from conductor.notion_client import NotionClient, _system_issue_properties


class NotionClientSystemIssueTest(unittest.TestCase):
    def _issue(self):
        return SystemIssueRecord(
            classification=SystemIssueClassification(
                issue_type="Неверное извлечение поля",
                severity="Средняя",
                database="TASKS",
                actual_result="Дата не извлечена",
                expected_result="Дата завтра",
                probable_cause="Техническая причина требует анализа",
                title="Дата неверная",
                correction_intent="CHANGE_FIELDS",
                correction_target_type="Task",
                corrected_fields=["date"],
            ),
            detection_method="Пользователь",
            status="Новая",
            input_data="Исходный ввод",
            description="Описание",
            solution="Требуется ручное исправление",
            detected_date="2026-05-20",
            fingerprint="fp",
        )

    def test_create_system_issue_uses_existing_database_id(self):
        client = NotionClient("token", "tasks", "study", "projects", system_issues_db="268ecbc58ba44b1787de101e49af1c73")
        with patch("conductor.notion_client.request_json", return_value={"url": "issue-url"}) as request_json:
            self.assertEqual(client.create_system_issue(self._issue()), "issue-url")
        payload = request_json.call_args.kwargs["payload"]
        self.assertEqual(payload["parent"], {"database_id": "268ecbc58ba44b1787de101e49af1c73"})

    def test_update_system_issue_only_updates_solution_and_status(self):
        client = NotionClient("token", "tasks", "study", "projects", system_issues_db="issues")
        with patch("conductor.notion_client.request_json") as request_json:
            client.update_system_issue("page-id", solution="Запись исправлена через Telegram feedback flow", status="В анализе")
        payload = request_json.call_args.kwargs["payload"]
        self.assertEqual(set(payload["properties"]), {"Решение", "Статус"})

    def test_system_issue_properties_keep_structured_context(self):
        properties = _system_issue_properties(self._issue())
        self.assertIn("Исходный ввод", properties["Входные данные"]["rich_text"][0]["text"]["content"])
        self.assertEqual(properties["Тип ошибки"], {"select": {"name": "Неверное извлечение поля"}})


if __name__ == "__main__":
    unittest.main()
