import unittest
from unittest.mock import Mock, patch

from conductor.models import classification_from_dict, normalize_effort
from conductor.notion_client import NotionClient
from conductor.openai_client import OpenAIClient
from conductor.service import (
    ConductorService,
    _apply_clarification_fallbacks,
    _apply_edit_to_recent,
    _format_created_summary,
    _resolve_pending_without_ai,
)


class ModelsTest(unittest.TestCase):
    def test_notion_project_lookup_reuses_supplied_catalog(self):
        client = NotionClient("token", "tasks", "study", "projects")
        client.list_projects = Mock(side_effect=AssertionError("catalog should not be reloaded"))

        project_id = client._find_project_id(
            " сырьевой   трейдинг ",
            projects=[{"id": "project-id", "name": "СЫРЬЕВОЙ ТРЕЙДИНГ"}],
        )

        self.assertEqual(project_id, "project-id")
        client.list_projects.assert_not_called()

    def test_notion_project_lookup_loads_catalog_as_fallback(self):
        client = NotionClient("token", "tasks", "study", "projects")
        client.list_projects = Mock(return_value=[{"id": "project-id", "name": "Проект"}])

        self.assertEqual(client._find_project_id("проект"), "project-id")
        client.list_projects.assert_called_once_with()

    def test_normalize_effort(self):
        self.assertEqual(normalize_effort(5), "5m")
        self.assertEqual(normalize_effort(14), "15m")
        self.assertEqual(normalize_effort(30), "30m")
        self.assertEqual(normalize_effort(60), "1h")
        self.assertEqual(normalize_effort(90), "2h+")

    def test_classification_from_dict(self):
        data = {
            "tasks": [
                {
                    "title": "Позвонить Марко",
                    "description": "Уточнить алюминий",
                    "desired_result": "Есть следующий шаг",
                    "project": "Сырьевой трейдинг",
                    "area": "Бизнес",
                    "due_date": "2026-05-21",
                    "effort_minutes": 15,
                    "priority": "P2",
                    "next_step": "Позвонить",
                    "confidence": 0.9,
                    "missing": [],
                }
            ],
            "studies": [],
            "notes": [],
        }
        result = classification_from_dict(data)
        self.assertEqual(result.tasks[0].title, "Позвонить Марко")
        self.assertEqual(result.tasks[0].effort_minutes, 15)

    def test_fallback_task_title_omits_metadata(self):
        client = OpenAIClient("", "unused", "unused")
        result = client._fallback(
            "Люба, задача: до завтра написать Марко по алюминию по проекту Сырьевой трейдинг, "
            "направление Бизнес. Оценка 15 минут. Желаемый результат: понять следующий шаг.",
            today="2026-05-20",
        )
        self.assertEqual(result.tasks[0].title, "Написать Марко по алюминию")
        self.assertEqual(result.tasks[0].project, "Сырьевой трейдинг")
        self.assertEqual(result.tasks[0].area, "Бизнес")
        self.assertEqual(result.tasks[0].due_date, "2026-05-21")
        self.assertEqual(result.tasks[0].desired_result, "понять следующий шаг")

    def test_fallback_study_question_omits_metadata(self):
        client = OpenAIClient("", "unused", "unused")
        result = client._fallback(
            "Люба, на изучение: до пятницы изучить доступные логистические пути через Веракрус "
            "по проекту Базовые масла, направление Бизнес. Нужна подробная справка.",
            today="2026-05-20",
        )
        self.assertEqual(result.studies[0].question, "Доступные логистические пути через Веракрус")
        self.assertEqual(result.studies[0].project, "Базовые масла")
        self.assertEqual(result.studies[0].research_type, "Глубокое")
        self.assertEqual(result.studies[0].result_format, "Подробная справка")

    def test_fallback_study_defaults_to_simple(self):
        client = OpenAIClient("", "unused", "unused")
        result = client._fallback(
            "Люба, на изучение: до пятницы исследовать рынок пластификаторов по проекту Сырьевой трейдинг, направление Бизнес.",
            today="2026-05-20",
        )
        self.assertEqual(result.studies[0].research_type, "Простое")
        self.assertEqual(result.studies[0].result_format, "Краткая справка")

    def test_postprocess_normalizes_project_name_and_area_from_catalog(self):
        client = OpenAIClient("", "unused", "unused")
        result = client._fallback(
            "Люба, задача: завтра написать Марко по проекту сырьевой трейдинг.",
            today="2026-05-20",
            projects=[{"name": "СЫРЬЕВОЙ ТРЕЙДИНГ", "area": "Бизнес", "status": "Active"}],
        )
        self.assertEqual(result.tasks[0].project, "СЫРЬЕВОЙ ТРЕЙДИНГ")
        self.assertEqual(result.tasks[0].area, "Бизнес")
        self.assertNotIn("project", result.tasks[0].missing)
        self.assertNotIn("area", result.tasks[0].missing)

    def test_postprocess_clears_unknown_project_when_catalog_exists(self):
        client = OpenAIClient("", "unused", "unused")
        result = client._fallback(
            "Люба, задача: завтра написать Марко по проекту неизвестный проект, направление Бизнес.",
            today="2026-05-20",
            projects=[{"name": "СЫРЬЕВОЙ ТРЕЙДИНГ", "area": "Бизнес", "status": "Active"}],
        )
        self.assertIsNone(result.tasks[0].project)
        self.assertIn("project", result.tasks[0].missing)

    def test_clarification_fallback_uses_obshchee_project(self):
        classification = classification_from_dict(
            {
                "tasks": [
                    {
                        "title": "Позвонить",
                        "description": "Позвонить клиенту",
                        "desired_result": "Совершенный звонок",
                        "project": None,
                        "area": None,
                        "due_date": "2026-05-21",
                        "effort_minutes": 15,
                        "priority": "P2",
                        "next_step": "Позвонить клиенту",
                        "confidence": 0.6,
                        "missing": ["project", "area"],
                    }
                ],
                "studies": [],
                "notes": [],
            }
        )
        result = _apply_clarification_fallbacks(classification)
        self.assertEqual(result.tasks[0].project, "Общее")
        self.assertEqual(result.tasks[0].area, "Прочее")
        self.assertEqual(result.tasks[0].missing, [])

    def test_process_audio_reports_transcription_failure(self):
        service = object.__new__(ConductorService)
        service.openai = Mock()
        service.openai.transcribe.side_effect = RuntimeError("insufficient_quota")
        service.telegram = Mock()

        result = service.process_audio("voice.ogg", b"123", content_type="audio/ogg", chat_id=42)

        self.assertEqual(result["tasks_created"], [])
        self.assertEqual(result["studies_created"], [])
        self.assertIn("insufficient_quota", result["errors"][0])
        self.assertEqual(service.telegram.send_message.call_count, 1)
        self.assertIn("Не смогла расшифровать голосовое", service.telegram.send_message.call_args.args[1])

    def test_transcribe_uses_fallback_model(self):
        client = OpenAIClient("key", "unused", "gpt-4o-mini-transcribe", "whisper-1")
        with patch("conductor.openai_client.request_multipart") as request_multipart:
            request_multipart.side_effect = [RuntimeError("primary failed"), {"text": "транскрипт"}]
            result = client.transcribe("voice.ogg", b"123", "audio/ogg")
        self.assertEqual(result, "транскрипт")
        self.assertEqual(request_multipart.call_count, 2)

    def test_pending_task_can_resolve_without_ai(self):
        pending_item = {
            "payload": {
                "type": "task",
                "item": {
                    "title": "Написать Марко",
                    "description": "Написать Марко по алюминию",
                    "desired_result": "Отправленное письмо",
                    "project": "СЫРЬЕВОЙ ТРЕЙДИНГ",
                    "area": "Бизнес",
                    "due_date": None,
                    "effort_minutes": 15,
                    "priority": "P2",
                    "next_step": "Написать Марко",
                    "confidence": 0.6,
                    "missing": ["due_date"],
                },
            },
            "questions": ["Какой срок исполнения?"],
        }
        result = _resolve_pending_without_ai(
            pending_item,
            "Завтра",
            today="2026-05-20",
            projects=[{"name": "СЫРЬЕВОЙ ТРЕЙДИНГ", "area": "Бизнес"}],
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.tasks[0].due_date, "2026-05-21")
        self.assertEqual(result.tasks[0].missing, [])
        self.assertGreaterEqual(result.tasks[0].confidence, 0.85)

    def test_edit_request_without_pending_returns_guidance(self):
        service = object.__new__(ConductorService)
        service.pending = Mock()
        service.pending.pop_oldest_for_chat.return_value = None
        service.recent = Mock()
        service.recent.get.return_value = None
        service.telegram = Mock()

        result = service.process_text("Поправь", chat_id=42)

        self.assertEqual(result["notes"], ["edit guidance sent"])
        service.telegram.send_message.assert_called_once()
        self.assertIn("Не поняла, что именно нужно поправить", service.telegram.send_message.call_args.args[1])

    def test_apply_edit_to_recent_updates_due_date(self):
        recent = {
            "type": "task",
            "url": "https://www.notion.so/test-12345678123412341234123456789012",
            "page_id": "12345678-1234-1234-1234-123456789012",
            "item": {
                "title": "Написать Марко",
                "description": "Написать Марко по алюминию",
                "desired_result": "Отправленное письмо",
                "project": "СЫРЬЕВОЙ ТРЕЙДИНГ",
                "area": "Бизнес",
                "due_date": "2026-05-21",
                "effort_minutes": 15,
                "priority": "P2",
                "next_step": "Написать Марко",
                "confidence": 0.9,
                "missing": [],
            },
        }
        updated = _apply_edit_to_recent(recent, "Исправь срок на пятницу", today="2026-05-20", projects=[])
        self.assertIsNotNone(updated)
        self.assertEqual(updated["item"]["due_date"], "2026-05-22")

    def test_created_summary_uses_explicit_multiline_format(self):
        classification = classification_from_dict(
            {
                "tasks": [
                    {
                        "title": "Написать Марко",
                        "description": "Написать Марко по алюминию",
                        "desired_result": "Отправленное письмо",
                        "project": "СЫРЬЕВОЙ ТРЕЙДИНГ",
                        "area": "Бизнес",
                        "due_date": "2026-05-21",
                        "effort_minutes": 15,
                        "priority": "P2",
                        "next_step": "Написать Марко",
                        "confidence": 0.9,
                        "missing": [],
                    }
                ],
                "studies": [],
                "notes": [],
            }
        )
        message = _format_created_summary(classification)
        self.assertIn("Добавила задачу: Написать Марко", message)
        self.assertIn("Направление: Бизнес", message)
        self.assertIn("Проект: СЫРЬЕВОЙ ТРЕЙДИНГ", message)
        self.assertIn("Дата исполнения: 2026-05-21", message)
        self.assertIn("Длительность работы: 15 минут", message)

    def test_birthday_reminder_turns_into_congratulation(self):
        client = OpenAIClient("", "unused", "unused")
        result = client._fallback(
            "Люба, задача: завтра напомни о дне рождения Марии по проекту Семья, направление Семья.",
            today="2026-05-20",
        )
        self.assertEqual(result.tasks[0].title, "Поздравить с днем рождения Марии")
        self.assertEqual(result.tasks[0].desired_result, "Совершенное поздравление")


if __name__ == "__main__":
    unittest.main()
