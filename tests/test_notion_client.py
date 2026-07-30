import unittest
from unittest.mock import patch

from conductor.models import ImprovementRecord, SystemIssueClassification, SystemIssueRecord
from conductor.notion_client import NotionClient, _improvement_properties, _system_issue_properties, notion_page_id_from_reference


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

    def test_list_recent_system_issues_uses_date_filters_and_limit(self):
        client = NotionClient("token", "tasks", "study", "projects", system_issues_db="issues")
        with patch("conductor.notion_client.request_json", return_value={"results": []}) as request_json:
            self.assertEqual(
                client.list_recent_system_issues(issue_type="Неверная классификация", database="BUY", days=90, limit=30),
                [],
            )
        payload = request_json.call_args.kwargs["payload"]
        self.assertEqual(payload["page_size"], 30)
        self.assertEqual(
            payload["filter"]["and"][1],
            {"property": "Тип ошибки", "select": {"equals": "Неверная классификация"}},
        )
        self.assertEqual(payload["filter"]["and"][2], {"property": "База данных", "select": {"equals": "BUY"}})

    def test_create_improvement_uses_existing_properties_and_relations(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="59332d8093464758baa4a86e077cbe59")
        improvement = ImprovementRecord(
            title="Уточнить классификацию товаров",
            description="Похожие ошибки Goods и Study.",
            suggested_change="Добавить правило и regression-тесты.",
            improvement_type="Правило",
            change_location="Правила Дирижёра",
            priority="Средний",
        )
        with patch("conductor.notion_client.request_json", return_value={"url": "improvement-url"}) as request_json:
            self.assertEqual(
                client.create_improvement(
                    improvement,
                    related_issue_urls=[
                        "https://www.notion.so/new-12345678123412341234123456789012",
                        "https://www.notion.so/a-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ],
                ),
                "improvement-url",
            )
        payload = request_json.call_args.kwargs["payload"]
        self.assertEqual(payload["parent"], {"database_id": "59332d8093464758baa4a86e077cbe59"})
        self.assertEqual(payload["properties"]["Статус"], {"select": {"name": "Идея"}})
        self.assertEqual(len(payload["properties"]["Какие ошибки исправляет"]["relation"]), 2)

    def test_improvement_properties_use_exact_notion_field_names(self):
        properties = _improvement_properties(
            ImprovementRecord(
                title="Уточнить правило",
                description="Описание",
                suggested_change="Что изменить",
                improvement_type="Правило",
                change_location="Правила Дирижёра",
                priority="Высокий",
            ),
            related_issue_urls=[],
        )

        self.assertEqual(properties["Какие ошибки исправляет"], {"relation": []})
        self.assertEqual(
            set(properties),
            {
                "Улучшение",
                "Описание",
                "Что изменить",
                "Тип улучшения",
                "Где изменить",
                "Приоритет",
                "Статус",
                "Какие ошибки исправляет",
            },
        )

    def test_find_open_improvements_uses_open_statuses_and_relation_filter(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        with patch("conductor.notion_client.request_json", return_value={"results": []}) as request_json:
            client.find_open_improvements_for_issues(
                related_issue_urls=["https://www.notion.so/new-12345678123412341234123456789012"],
                title="Уточнить классификацию товаров",
                improvement_type="Правило",
                change_location="Правила Дирижёра",
            )
        filters = request_json.call_args.kwargs["payload"]["filter"]["and"]
        statuses = {item["select"]["equals"] for item in filters[0]["or"]}
        self.assertEqual(statuses, {"Идея", "В работе", "Отложено"})
        self.assertEqual(filters[1]["or"][0]["property"], "Какие ошибки исправляет")

    def test_notion_page_reference_accepts_uuid_without_dashes(self):
        self.assertEqual(
            notion_page_id_from_reference("12345678123412341234123456789012"),
            "12345678-1234-1234-1234-123456789012",
        )

    def test_notion_page_reference_accepts_uuid_with_dashes(self):
        self.assertEqual(
            notion_page_id_from_reference("12345678-1234-1234-1234-123456789012"),
            "12345678-1234-1234-1234-123456789012",
        )

    def test_notion_page_reference_accepts_notion_url_and_app_url(self):
        self.assertEqual(
            notion_page_id_from_reference("https://www.notion.so/Test-12345678123412341234123456789012?pvs=4"),
            "12345678-1234-1234-1234-123456789012",
        )
        self.assertEqual(
            notion_page_id_from_reference("https://app.notion.com/workspace/Test-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )

    def test_invalid_notion_page_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid Notion page reference"):
            notion_page_id_from_reference("https://www.notion.so/not-a-page")

    def test_database_id_is_rejected_as_relation_page_id(self):
        client = NotionClient(
            "token",
            "tasks",
            "study",
            "projects",
            system_issues_db="268ecbc58ba44b1787de101e49af1c73",
            improvements_db="59332d8093464758baa4a86e077cbe59",
        )
        with self.assertRaisesRegex(ValueError, "database ID"):
            client.create_improvement(
                ImprovementRecord(
                    title="Уточнить правило",
                    description="Описание",
                    suggested_change="Что изменить",
                    improvement_type="Правило",
                    change_location="Правила Дирижёра",
                    priority="Средний",
                ),
                related_issue_urls=["268ecbc58ba44b1787de101e49af1c73"],
            )

    def test_unknown_improvement_select_value_is_rejected_before_request(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        with self.assertRaisesRegex(ValueError, "Unknown Improvement type"):
            client.create_improvement(
                ImprovementRecord(
                    title="Уточнить правило",
                    description="Описание",
                    suggested_change="Что изменить",
                    improvement_type="GitHub",
                    change_location="Правила Дирижёра",
                    priority="Средний",
                ),
                related_issue_urls=[],
            )

    def test_create_improvement_always_uses_idea_status(self):
        properties = _improvement_properties(
            ImprovementRecord(
                title="Уточнить правило",
                description="Описание",
                suggested_change="Что изменить",
                improvement_type="Правило",
                change_location="Правила Дирижёра",
                priority="Средний",
                status="В работе",
            ),
            related_issue_urls=[],
        )

        self.assertEqual(properties["Статус"], {"select": {"name": "Идея"}})

    def test_get_improvement_reads_forward_issue_relation(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        page = {
            "id": "99999999-9999-9999-9999-999999999999",
            "url": "improvement-url",
            "properties": {
                "Улучшение": {"title": [{"plain_text": "Уточнить Goods"}]},
                "Статус": {"select": {"name": "Идея"}},
                "Тип улучшения": {"select": {"name": "Правило"}},
                "Где изменить": {"select": {"name": "Правила Дирижёра"}},
                "Какие ошибки исправляет": {
                    "relation": [{"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}],
                },
            },
        }
        with patch("conductor.notion_client.request_json", return_value=page) as request_json:
            improvement = client.get_improvement("99999999999999999999999999999999")

        self.assertEqual(improvement.title, "Уточнить Goods")
        self.assertEqual(improvement.related_issue_urls, ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"])
        request_json.assert_called_once()

    def test_get_system_issues_by_references_reads_each_page(self):
        client = NotionClient("token", "tasks", "study", "projects", system_issues_db="issues")
        page = {
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "url": "issue-url",
            "properties": {
                "Краткое описание ошибки": {"title": [{"plain_text": "Goods попал в Study"}]},
                "Тип ошибки": {"select": {"name": "Неверная классификация"}},
                "Критичность": {"select": {"name": "Средняя"}},
                "База данных": {"select": {"name": "BUY"}},
                "Входные данные": {"rich_text": [{"plain_text": "Купить покрышку"}]},
                "Описание": {"rich_text": [{"plain_text": "Ожидался Goods"}]},
                "Решение": {"rich_text": [{"plain_text": "Исправить правило"}]},
                "Дата обнаружения": {"date": {"start": "2026-07-30"}},
            },
        }
        with patch("conductor.notion_client.request_json", return_value=page):
            issues = client.get_system_issues_by_references(["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].database, "BUY")

    def test_save_improvement_technical_spec_archives_only_managed_section(self):
        client = NotionClient("token", "tasks", "study", "projects", improvements_db="improvements")
        children = {
            "results": [
                self._block("user-before", "paragraph", "Пользовательский текст"),
                self._block("managed-title", "heading_2", "Техническое задание для Codex"),
                self._block("managed-body", "paragraph", "Старое ТЗ"),
                self._block("managed-end", "paragraph", "<!-- CONDUCTOR_TECH_SPEC_END -->"),
                self._block("user-after", "paragraph", "Еще пользовательский текст"),
            ]
        }

        with patch("conductor.notion_client.request_json") as request_json:
            request_json.side_effect = [children, {}, {}, {}, {"id": "append"}]
            client.save_improvement_technical_spec("99999999999999999999999999999999", "# Новое ТЗ", today="2026-07-30")

        archived_urls = [call.args[1] for call in request_json.call_args_list if call.args[0] == "PATCH" and call.kwargs.get("payload") == {"archived": True}]
        self.assertEqual(
            archived_urls,
            [
                "https://api.notion.com/v1/blocks/managed-title",
                "https://api.notion.com/v1/blocks/managed-body",
                "https://api.notion.com/v1/blocks/managed-end",
            ],
        )
        append_payload = request_json.call_args_list[-1].kwargs["payload"]
        self.assertEqual(append_payload["children"][0]["type"], "heading_2")
        self.assertIn("CONDUCTOR_TECH_SPEC_END", append_payload["children"][-1]["paragraph"]["rich_text"][0]["text"]["content"])

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


if __name__ == "__main__":
    unittest.main()
