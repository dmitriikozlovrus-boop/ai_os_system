import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from conductor.task_sync import (
    SyncResult,
    TaskSyncService,
    _fingerprint,
    _match_key_notion,
    _match_key_todoist,
    _notion_properties_from_todoist,
    _priority_to_strategic,
    _strategic_to_priority,
)
from conductor.todoist_client import TodoistClient, _task_payload, todoist_priority


class TodoistMappingTest(unittest.TestCase):
    def test_priority_mapping_round_trip(self):
        self.assertEqual(todoist_priority(1), "P1")
        self.assertEqual(todoist_priority(4), "P4")
        self.assertEqual(_strategic_to_priority("9"), "P1")
        self.assertEqual(_strategic_to_priority("7"), "P2")
        self.assertEqual(_priority_to_strategic("P3"), "5")

    def test_todoist_payload_contains_dates(self):
        payload = _task_payload(
            {
                "title": "Подготовить письмо",
                "description": "Черновик",
                "priority": "P1",
                "due_date": "2026-06-13",
                "deadline": "2026-06-15",
            }
        )
        self.assertEqual(payload["content"], "Подготовить письмо")
        self.assertEqual(payload["priority"], 1)
        self.assertEqual(payload["due_date"], "2026-06-13")
        self.assertEqual(payload["deadline_date"], "2026-06-15")

    def test_notion_project_becomes_todoist_label(self):
        payload = _task_payload(
            {
                "title": "Подготовить письмо",
                "description": "",
                "priority": "P2",
                "project_name": "AI DESIGN SYSTEM",
            }
        )
        self.assertEqual(payload["labels"], ["AI DESIGN SYSTEM"])

    def test_todoist_task_does_not_set_notion_project(self):
        properties = _notion_properties_from_todoist(
            {
                "content": "Подготовить письмо",
                "priority": 3,
                "labels": ["AI DESIGN SYSTEM"],
                "due": {"date": "2026-06-13"},
                "deadline": {"date": "2026-06-15"},
                "is_completed": False,
            }
        )
        self.assertIn("Task", properties)
        self.assertIn("Статус", properties)
        self.assertIn("Срок выполнения", properties)
        self.assertIn("Deadline", properties)
        self.assertNotIn("Проект", properties)

    def test_existing_tasks_match_by_normalized_title_and_due_date(self):
        notion = {"title": "  Подготовить   письмо ", "due_date": "2026-06-13"}
        todoist = {"content": "подготовить письмо", "due": {"date": "2026-06-13"}}
        self.assertEqual(_match_key_notion(notion), _match_key_todoist(todoist))


class TaskSyncTest(unittest.TestCase):
    def test_linked_unchanged_task_does_not_sync_again(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        with tempfile.TemporaryDirectory() as directory:
            service = TaskSyncService("notion", "tasks", "projects", todoist, str(Path(directory) / "state.json"))
            service._mark_notion_sync = Mock()
            notion = {
                "page_id": "page-1",
                "title": "Task",
                "description": "",
                "status": "Backlog",
                "priority": "P2",
                "due_date": "2026-06-13",
                "deadline": None,
                "todoist_id": "todo-1",
                "last_edited_time": "2026-06-11T10:00:00Z",
            }
            todo = {
                "id": "todo-1",
                "content": "Task",
                "description": "",
                "priority": 3,
                "due": {"date": "2026-06-13"},
                "deadline": None,
                "is_completed": False,
                "updated_at": "2026-06-11T10:00:00Z",
            }
            state = {
                "page-1": {
                    "notion": _fingerprint(notion),
                    "todoist": _fingerprint(todo),
                    "todoist_id": "todo-1",
                }
            }
            result = SyncResult(errors=[])
            service._sync_notion_task(notion, {"todo-1": todo}, state, result)
            todoist.update_task.assert_not_called()
            self.assertEqual(result.notion_to_todoist, 0)

    def test_webhook_completion_updates_notion(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        with tempfile.TemporaryDirectory() as directory:
            service = TaskSyncService("notion", "tasks", "projects", todoist, str(Path(directory) / "state.json"))
            service._find_notion_by_todoist_id = Mock(return_value={"page_id": "page-1"})
            service._update_notion_status = Mock()
            result = service.handle_todoist_event({"event_name": "item:completed", "event_data": {"id": "todo-1"}})
            service._update_notion_status.assert_called_once_with("page-1", "Done")
            self.assertEqual(result["action"], "completed_in_notion")

    def test_periodic_sync_completion_updates_notion(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        with tempfile.TemporaryDirectory() as directory:
            service = TaskSyncService("notion", "tasks", "projects", todoist, str(Path(directory) / "state.json"))
            service._list_notion_projects = Mock(return_value={})
            service._update_notion_from_todoist = Mock()
            notion = {
                "page_id": "page-1",
                "title": "Task",
                "description": "",
                "status": "Backlog",
                "priority": "P2",
                "due_date": None,
                "deadline": None,
                "todoist_id": "todo-1",
                "last_edited_time": "2026-06-11T10:00:00Z",
            }
            todo = {"id": "todo-1", "content": "Task", "priority": 2, "is_completed": True}
            result = SyncResult(errors=[])
            service._sync_notion_task(notion, {"todo-1": todo}, {}, result)
            service._update_notion_from_todoist.assert_called_once_with("page-1", todo)
            todoist.reopen_task.assert_not_called()
            self.assertEqual(result.todoist_to_notion, 1)

    def test_explicit_notion_reopen_reopens_todoist(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        with tempfile.TemporaryDirectory() as directory:
            service = TaskSyncService("notion", "tasks", "projects", todoist, str(Path(directory) / "state.json"))
            service._mark_notion_sync = Mock()
            notion = {
                "page_id": "page-1",
                "title": "Task",
                "description": "",
                "status": "Backlog",
                "priority": "P2",
                "due_date": None,
                "deadline": None,
                "todoist_id": "todo-1",
                "last_edited_time": "2026-06-11T11:00:00Z",
            }
            previous_notion = {**notion, "status": "Done"}
            todo = {"id": "todo-1", "content": "Task", "priority": 2, "is_completed": True}
            state = {
                "page-1": {
                    "notion": _fingerprint(previous_notion),
                    "todoist": _fingerprint(todo),
                    "todoist_id": "todo-1",
                }
            }
            result = SyncResult(errors=[])
            service._sync_notion_task(notion, {"todo-1": todo}, state, result)
            todoist.reopen_task.assert_called_once_with("todo-1")
            todoist.update_task.assert_called_once_with("todo-1", notion)
            self.assertEqual(result.notion_to_todoist, 1)

    def test_all_notion_projects_become_todoist_labels(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        todoist.list_labels.return_value = [{"name": "Existing Project"}]
        with tempfile.TemporaryDirectory() as directory:
            service = TaskSyncService("notion", "tasks", "projects", todoist, str(Path(directory) / "state.json"))
            created = service._ensure_todoist_project_labels(
                {
                    "existing project": {"id": "project-1", "name": "Existing Project"},
                    "new project": {"id": "project-2", "name": "New Project"},
                }
            )
            todoist.create_label.assert_called_once_with("New Project")
            self.assertEqual(created, 1)

    def test_notion_project_overwrites_todoist_labels(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        with tempfile.TemporaryDirectory() as directory:
            service = TaskSyncService("notion", "tasks", "projects", todoist, str(Path(directory) / "state.json"))
            notion = {
                "page_id": "page-1",
                "title": "Task",
                "description": "",
                "status": "Backlog",
                "priority": "P2",
                "due_date": None,
                "deadline": None,
                "todoist_id": "todo-1",
                "project_name": "Notion Project",
                "last_edited_time": "2026-06-11T10:00:00Z",
            }
            todo = {
                "id": "todo-1",
                "content": "Task",
                "description": "",
                "priority": 2,
                "labels": ["Todoist Project"],
                "is_completed": False,
                "updated_at": "2026-06-11T10:00:00Z",
            }
            state = {
                "page-1": {
                    "notion": _fingerprint(notion),
                    "todoist": _fingerprint({**todo, "labels": ["Notion Project"]}),
                    "todoist_id": "todo-1",
                }
            }
            result = SyncResult(errors=[])
            service._sync_notion_task(notion, {"todo-1": todo}, state, result)
            todoist.update_task_labels.assert_called_once_with("todo-1", ["Notion Project"])

    def test_completed_notion_task_is_created_and_closed_in_todoist(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        todoist.create_task.return_value = "todo-1"
        with tempfile.TemporaryDirectory() as directory:
            service = TaskSyncService("notion", "tasks", "projects", todoist, str(Path(directory) / "state.json"))
            service._set_notion_todoist_id = Mock()
            notion = {
                "page_id": "page-1",
                "title": "Завершённая задача",
                "description": "",
                "status": "Done",
                "priority": "P3",
                "due_date": None,
                "deadline": None,
                "todoist_id": "",
                "project_name": "AI DESIGN SYSTEM",
                "last_edited_time": "2026-06-11T10:00:00Z",
            }
            result = SyncResult(errors=[])
            service._sync_notion_task(notion, {}, {}, result)
            todoist.create_task.assert_called_once_with(notion)
            todoist.close_task.assert_called_once_with("todo-1")
            self.assertEqual(result.completed, 1)


if __name__ == "__main__":
    unittest.main()
