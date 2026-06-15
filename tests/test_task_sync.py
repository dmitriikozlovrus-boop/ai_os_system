import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from conductor.http import HttpError
from conductor.task_sync import (
    MANAGED_TODOIST_LABELS,
    PRIMARY_SYNC_CONTRACT_VERSION,
    SyncResult,
    TaskSyncService,
    _fingerprint,
    _managed_labels,
    _match_key_notion,
    _match_key_todoist,
    _notion_properties_from_todoist,
    _notion_routing_from_todoist,
    _notion_sync_timestamps,
    _notion_stored_state,
    _parse_time,
    _priority_to_strategic,
    _retry_after,
    _strategic_to_priority,
)
from conductor.todoist_client import TodoistClient, _task_payload, todoist_priority


def service(todoist=None, directory=None, **kwargs):
    todoist = todoist or Mock(spec=TodoistClient)
    todoist.enabled = True
    todoist.api_token = "token"
    state_path = str(Path(directory or tempfile.gettempdir()) / "state.json")
    snapshot_path = str(Path(directory or tempfile.gettempdir()) / "snapshot.json")
    return TaskSyncService(
        "notion",
        "tasks",
        "projects",
        todoist,
        state_path,
        streams_database_id="streams",
        snapshot_path=snapshot_path,
        **kwargs,
    )


class TodoistMappingTest(unittest.TestCase):
    def test_priority_mapping_round_trip(self):
        self.assertEqual(todoist_priority(4), "P1")
        self.assertEqual(_strategic_to_priority("7"), "P2")
        self.assertEqual(_priority_to_strategic("P3"), "5")

    def test_todoist_payload_routes_by_project_and_section_not_project_label(self):
        payload = _task_payload(
            {
                "title": "Подготовить письмо",
                "project_name": "Old project label",
                "todoist_project_id": "todo-project-1",
                "todoist_section_id": "section-1",
                "managed_labels": ["письмо", "низкая_энергия"],
            }
        )
        self.assertEqual(payload["project_id"], "todo-project-1")
        self.assertEqual(payload["section_id"], "section-1")
        self.assertEqual(payload["labels"], ["письмо", "низкая_энергия"])
        self.assertNotIn("Old project label", payload["labels"])

    def test_only_operational_labels_are_managed(self):
        self.assertEqual(
            _managed_labels(["Project A", "встреча", "@пятиминутное_дело", "custom"]),
            ["встреча", "пятиминутное_дело"],
        )

    def test_todoist_project_and_section_become_notion_routing(self):
        properties = _notion_routing_from_todoist(
            {"project_id": "todo-project-1", "section_id": "section-1"},
            {
                "project a": {
                    "id": "notion-project-1",
                    "name": "Project A",
                    "stream_id": "stream-business",
                    "todoist_project_id": "todo-project-1",
                }
            },
            {"бизнес": {"id": "stream-business", "name": "БИЗНЕС"}},
            [{"id": "todo-project-1", "name": "Project A"}],
            [{"id": "section-1", "name": "Сделать", "project_id": "todo-project-1"}],
        )
        self.assertEqual(properties["Проект"], {"relation": [{"id": "notion-project-1"}]})
        self.assertEqual(properties["Stream"], {"relation": [{"id": "stream-business"}]})
        self.assertEqual(properties["Раздел"]["rich_text"][0]["text"]["content"], "Сделать")
        self.assertEqual(properties["Todoist Section ID"]["rich_text"][0]["text"]["content"], "section-1")

    def test_same_section_name_in_another_project_does_not_collide(self):
        properties = _notion_routing_from_todoist(
            {"project_id": "todo-project-2", "section_id": "section-2"},
            {
                "a": {"id": "notion-a", "stream_id": "", "todoist_project_id": "todo-project-1"},
                "b": {"id": "notion-b", "stream_id": "", "todoist_project_id": "todo-project-2"},
            },
            {},
            [{"id": "todo-project-1"}, {"id": "todo-project-2"}],
            [
                {"id": "section-1", "name": "Сделать", "project_id": "todo-project-1"},
                {"id": "section-2", "name": "Сделать", "project_id": "todo-project-2"},
            ],
        )
        self.assertEqual(properties["Проект"], {"relation": [{"id": "notion-b"}]})
        self.assertEqual(properties["Todoist Section ID"]["rich_text"][0]["text"]["content"], "section-2")

    def test_unmapped_todoist_project_does_not_leave_orphan_section_in_notion(self):
        properties = _notion_routing_from_todoist(
            {"project_id": "unmapped-project", "section_id": "section-1"},
            {},
            {},
            [{"id": "unmapped-project", "name": "Unmapped"}],
            [{"id": "section-1", "name": "Old section", "project_id": "unmapped-project"}],
        )
        self.assertEqual(properties["Проект"], {"relation": []})
        self.assertEqual(properties["Stream"], {"relation": []})
        self.assertEqual(properties["Раздел"], {"rich_text": []})
        self.assertEqual(properties["Todoist Section ID"], {"rich_text": []})

    def test_todoist_fields_include_managed_labels(self):
        properties = _notion_properties_from_todoist(
            {"content": "Task", "labels": ["Project A", "анализ", "custom"]}
        )
        self.assertEqual(properties["Метки Todoist"], {"multi_select": [{"name": "анализ"}]})

    def test_todoist_sync_timestamps_are_visible_in_notion(self):
        properties = _notion_sync_timestamps(
            {"added_at": "2026-06-15T10:00:00Z", "updated_at": "2026-06-15T11:00:00Z"}
        )
        self.assertEqual(properties["Todoist created at"], {"date": {"start": "2026-06-15T10:00:00Z"}})
        self.assertEqual(properties["Todoist updated at"], {"date": {"start": "2026-06-15T11:00:00Z"}})
        self.assertIn("Last synced at", properties)

    def test_existing_tasks_match_by_normalized_title_and_due_date(self):
        notion = {"title": "  Подготовить   письмо ", "due_date": "2026-06-13"}
        todoist = {"content": "подготовить письмо", "due": {"date": "2026-06-13"}}
        self.assertEqual(_match_key_notion(notion), _match_key_todoist(todoist))

    def test_parse_time_and_stored_hashes(self):
        self.assertEqual(_parse_time("2026-06-12T10:00:00Z"), datetime(2026, 6, 12, 10, tzinfo=timezone.utc))
        self.assertEqual(
            _notion_stored_state({"todoist_id": "1", "sync_notion_hash": "n", "sync_todoist_hash": "t"}),
            {"notion": "n", "todoist": "t", "todoist_id": "1"},
        )


class SafetyTest(unittest.TestCase):
    def test_observe_mode_writes_snapshot_and_performs_no_remote_writes(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        todoist.list_projects.return_value = [{"id": "tp-1", "name": "Project A"}]
        todoist.list_sections.return_value = [{"id": "s-1", "name": "Doing", "project_id": "tp-1"}]
        todoist.list_labels.return_value = [{"id": "l-1", "name": "анализ"}]
        todoist.list_tasks.return_value = [{"id": "t-1", "project_id": "tp-1", "section_id": "s-1"}]
        with tempfile.TemporaryDirectory() as directory:
            sync = service(todoist, directory, mode="observe")
            sync._list_notion_tasks = Mock(return_value=[])
            sync._list_notion_projects = Mock(return_value={})
            sync._list_notion_streams = Mock(return_value={})
            result = sync.sync()
            snapshot = json.loads(Path(result["snapshot_path"]).read_text(encoding="utf-8"))
            report = sync.read_inventory_report()
            summary = sync.read_inventory_summary()
        self.assertEqual(result["mode"], "observe")
        self.assertEqual(snapshot["todoist"]["active_tasks"][0]["id"], "t-1")
        self.assertTrue(report["available"])
        self.assertEqual(report["todoist_projects"][0]["active_task_count"], 1)
        self.assertNotIn("t-1", json.dumps(report))
        self.assertEqual(summary["inventory"]["todoist_active_tasks"], 1)
        self.assertNotIn("todoist_projects", summary)
        todoist.create_project.assert_not_called()
        todoist.create_task.assert_not_called()
        todoist.update_task_location.assert_not_called()
        todoist.update_task_labels.assert_not_called()

    def test_observe_webhook_is_ignored(self):
        sync = service(mode="observe")
        result = sync.handle_todoist_event({"event_name": "item:updated", "event_data": {"id": "t-1"}})
        self.assertEqual(result["reason"], "sync is in observe mode")

    def test_projects_mode_webhook_is_ignored(self):
        sync = service(mode="projects")
        result = sync.handle_todoist_event({"event_name": "item:updated", "event_data": {"id": "t-1"}})
        self.assertEqual(result["reason"], "sync is in projects mode")

    def test_todoist_primary_updates_inbox_task_and_clears_notion_routing(self):
        with tempfile.TemporaryDirectory() as directory:
            sync = service(mode="todoist-primary", directory=directory)
            notion_task = {"page_id": "p-1", "status": "Backlog"}
            sync._find_notion_by_todoist_id = Mock(return_value=notion_task)
            sync._list_notion_projects = Mock(return_value={})
            sync._list_notion_streams = Mock(return_value={})
            sync.todoist.list_projects.return_value = [{"id": "inbox", "name": "Inbox"}]
            sync.todoist.list_sections.return_value = []
            sync.todoist.get_task.return_value = {"id": "t-1", "project_id": "inbox"}
            sync._write_todoist_snapshot_to_notion = Mock()
            sync._persist_sync_state_to_notion = Mock()
            sync._save_state = Mock()
            result = sync.handle_todoist_event({"event_name": "item:updated", "event_data": {"id": "t-1"}})
        self.assertEqual(result["action"], "upserted_in_notion")
        sync._write_todoist_snapshot_to_notion.assert_called_once()

    def test_todoist_primary_updates_notion_for_mapped_project(self):
        with tempfile.TemporaryDirectory() as directory:
            sync = service(mode="todoist-primary", directory=directory)
            notion_task = {"page_id": "p-1", "status": "Backlog"}
            sync._find_notion_by_todoist_id = Mock(return_value=notion_task)
            sync._list_notion_projects = Mock(
                return_value={"a": {"id": "np-1", "name": "A", "stream_id": "", "todoist_project_id": "tp-1"}}
            )
            sync._list_notion_streams = Mock(return_value={})
            sync.todoist.list_projects.return_value = [{"id": "tp-1", "name": "A"}]
            sync.todoist.list_sections.return_value = []
            sync.todoist.get_task.return_value = {"id": "t-1", "project_id": "tp-1"}
            sync._write_todoist_snapshot_to_notion = Mock()
            sync._persist_sync_state_to_notion = Mock()
            sync._save_state = Mock()
            result = sync.handle_todoist_event({"event_name": "item:updated", "event_data": {"id": "t-1"}})
        self.assertEqual(result["action"], "upserted_in_notion")
        sync._write_todoist_snapshot_to_notion.assert_called_once()

    def test_delayed_todoist_webhook_does_not_overwrite_newer_notion_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            sync = service(mode="todoist-primary", directory=directory)
            notion = {
                "page_id": "p-1",
                "todoist_id": "t-1",
                "title": "Newer Notion edit",
                "status": "Backlog",
                "last_edited_time": "2026-06-15T12:00:00Z",
            }
            todo = {
                "id": "t-1",
                "content": "Older Todoist edit",
                "project_id": "inbox",
                "updated_at": "2026-06-15T11:00:00Z",
            }
            sync._find_notion_by_todoist_id = Mock(return_value=notion)
            sync._list_notion_projects = Mock(return_value={})
            sync._list_notion_streams = Mock(return_value={})
            sync.todoist.list_projects.return_value = [{"id": "inbox", "name": "Inbox", "is_inbox_project": True}]
            sync.todoist.list_sections.return_value = []
            sync.todoist.get_task.return_value = todo
            sync._load_state = Mock(
                return_value={
                    "__meta__": {"primary_sync_contract_version": PRIMARY_SYNC_CONTRACT_VERSION},
                    "p-1": {"notion": "old-n", "todoist": "old-t", "todoist_id": "t-1"},
                }
            )
            sync._update_todoist_from_notion_primary = Mock()
            sync._persist_sync_state_to_notion = Mock()
            sync._save_state = Mock()
            sync.handle_todoist_event({"event_name": "item:updated", "event_data": {"id": "t-1"}})
        sync._update_todoist_from_notion_primary.assert_called_once()

    def test_todoist_primary_periodic_sync_creates_missing_todoist_task_in_project(self):
        sync = service(mode="todoist-primary")
        notion = {
            "page_id": "p-1",
            "title": "From Luba",
            "description": "",
            "status": "Backlog",
            "todoist_id": "",
            "todoist_project_id": "tp-1",
            "todoist_section_id": "",
            "managed_labels": [],
        }
        sync.todoist.create_task.return_value = "t-new"
        sync._set_notion_todoist_id = Mock()
        result = SyncResult(errors=[], mode="todoist-primary")
        sync._sync_todoist_primary(
            [notion],
            [],
            {},
            result,
            {},
            {},
            [{"id": "tp-1", "name": "Project"}],
            [],
        )
        sync.todoist.create_task.assert_called_once_with(notion)
        sync._set_notion_todoist_id.assert_called_once_with("p-1", "t-new", "Synced")
        self.assertEqual(result.notion_to_todoist, 1)

    def test_primary_contract_bootstrap_forces_todoist_to_notion(self):
        sync = service(mode="todoist-primary")
        notion = {
            "page_id": "p-1",
            "title": "Newer Notion title",
            "status": "Backlog",
            "todoist_id": "t-1",
        }
        todo = {"id": "t-1", "content": "Current Todoist title", "project_id": "inbox"}
        state = {"p-1": {"notion": "old-n", "todoist": "old-t", "todoist_id": "t-1"}}
        result = SyncResult(errors=[], mode="todoist-primary")
        sync._write_todoist_snapshot_to_notion = Mock()
        sync._persist_sync_state_to_notion = Mock()
        sync._sync_todoist_primary(
            [notion],
            [todo],
            state,
            result,
            {},
            {},
            [{"id": "inbox", "name": "Inbox", "is_inbox_project": True}],
            [],
            bootstrap=True,
        )
        sync._write_todoist_snapshot_to_notion.assert_called_once()
        sync.todoist.update_task.assert_not_called()
        self.assertEqual(result.todoist_to_notion, 1)

    def test_notion_done_requests_todoist_completion_review(self):
        sync = service(mode="todoist-primary")
        notion = {
            "page_id": "p-1",
            "todoist_id": "t-1",
            "title": "Task",
            "description": "",
            "status": "Done",
            "priority": "P4",
            "due_date": None,
            "deadline": None,
            "project_name": "",
            "stream_name": "",
            "section_name": "",
            "todoist_section_id": "",
            "managed_labels": [],
            "last_edited_time": "2026-06-15T12:00:00Z",
        }
        todo = {
            "id": "t-1",
            "content": "Task",
            "description": "",
            "priority": 1,
            "labels": [],
            "project_id": "inbox",
            "is_completed": False,
            "updated_at": "2026-06-15T11:00:00Z",
        }
        state = {
            "p-1": {
                "notion": "older-notion",
                "todoist": _fingerprint(todo),
                "todoist_id": "t-1",
            }
        }
        result = SyncResult(errors=[], mode="todoist-primary")
        sync._update_todoist_from_notion_primary = Mock()
        sync._request_completion_review = Mock()
        sync._reconcile_primary_linked_task(notion, todo, state, result, {}, {}, [], [])
        sync._update_todoist_from_notion_primary.assert_called_once()
        sync._request_completion_review.assert_called_once_with(notion, todo)
        sync.todoist.close_task.assert_not_called()

    def test_newer_todoist_change_cancels_stale_notion_completion_request(self):
        sync = service(mode="todoist-primary")
        notion = {
            "page_id": "p-1",
            "todoist_id": "t-1",
            "title": "Task",
            "status": "Done",
            "last_edited_time": "2026-06-15T11:00:00Z",
        }
        todo = {
            "id": "t-1",
            "content": "Task updated later",
            "project_id": "inbox",
            "is_completed": False,
            "updated_at": "2026-06-15T12:00:00Z",
        }
        state = {"p-1": {"notion": "old-n", "todoist": "old-t", "todoist_id": "t-1"}}
        result = SyncResult(errors=[], mode="todoist-primary")
        sync._write_todoist_snapshot_to_notion = Mock()
        sync._request_completion_review = Mock()
        sync._reconcile_primary_linked_task(notion, todo, state, result, {}, {}, [], [])
        sync._write_todoist_snapshot_to_notion.assert_called_once()
        sync._request_completion_review.assert_not_called()

    def test_completion_review_status_is_not_cleared_on_unchanged_sync(self):
        sync = service(mode="todoist-primary")
        notion = {
            "page_id": "p-1",
            "todoist_id": "t-1",
            "title": "Task",
            "status": "Waiting",
            "sync_status": "Review required",
            "sync_error": "Review it",
        }
        todo = {"id": "t-1", "content": "Task", "is_completed": False}
        state = {"p-1": {"notion": _fingerprint(notion), "todoist": _fingerprint(todo), "todoist_id": "t-1"}}
        result = SyncResult(errors=[], mode="todoist-primary")
        sync._mark_notion_sync = Mock()
        sync._reconcile_primary_linked_task(notion, todo, state, result, {}, {}, [], [])
        sync._mark_notion_sync.assert_not_called()

    def test_newer_todoist_change_wins_conflict(self):
        sync = service(mode="todoist-primary")
        notion = {
            "page_id": "p-1",
            "todoist_id": "t-1",
            "title": "Notion edit",
            "description": "",
            "status": "Backlog",
            "priority": "P4",
            "due_date": None,
            "deadline": None,
            "project_name": "",
            "stream_name": "",
            "section_name": "",
            "todoist_section_id": "",
            "managed_labels": [],
            "last_edited_time": "2026-06-15T11:00:00Z",
        }
        todo = {
            "id": "t-1",
            "content": "Newer Todoist edit",
            "description": "",
            "priority": 1,
            "labels": [],
            "project_id": "inbox",
            "is_completed": False,
            "updated_at": "2026-06-15T12:00:00Z",
        }
        state = {"p-1": {"notion": "old-n", "todoist": "old-t", "todoist_id": "t-1"}}
        result = SyncResult(errors=[], mode="todoist-primary")
        sync._write_todoist_snapshot_to_notion = Mock()
        sync._reconcile_primary_linked_task(notion, todo, state, result, {}, {}, [], [])
        sync._write_todoist_snapshot_to_notion.assert_called_once()
        sync.todoist.update_task.assert_not_called()

    def test_runtime_mode_override_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            sync = service(mode="observe", directory=directory)
            sync.set_runtime_mode("todoist-primary")
            restarted = service(mode="observe", directory=directory)
        self.assertEqual(restarted.mode, "todoist-primary")

    def test_move_labeled_inbox_tasks_only_moves_unique_project_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            sync = service(mode="todoist-primary", directory=directory)
            sync._list_notion_projects = Mock(
                return_value={
                    "a": {"name": "Project A", "todoist_project_id": "tp-a"},
                    "b": {"name": "Project B", "todoist_project_id": "tp-b"},
                }
            )
            sync.todoist.list_projects.return_value = [{"id": "inbox", "name": "Inbox", "is_inbox_project": True}]
            sync.todoist.list_tasks.return_value = [
                {"id": "move", "project_id": "inbox", "labels": ["Project A", "звонок"]},
                {"id": "ambiguous", "project_id": "inbox", "labels": ["Project A", "Project B"]},
                {"id": "unmatched", "project_id": "inbox", "labels": ["звонок"]},
                {"id": "already-moved", "project_id": "tp-a", "labels": ["Project B"]},
            ]
            sync.todoist.update_task_locations_batch.return_value = {}
            result = sync.move_labeled_inbox_tasks()
        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["ambiguous"], 1)
        self.assertEqual(result["left_without_project_label"], 1)
        sync.todoist.update_task_locations_batch.assert_called_once_with([("move", "tp-a")])
        self.assertEqual(sync.mode, "todoist-primary")

    def test_missing_task_is_not_cancelled_by_default(self):
        sync = service(mode="write")
        sync._update_notion_status = Mock()
        with self.assertRaisesRegex(RuntimeError, "manual review"):
            sync._sync_notion_task(
                {"page_id": "p-1", "title": "Task", "status": "Backlog", "todoist_id": "missing"},
                {},
                {},
                SyncResult(errors=[]),
            )
        sync._update_notion_status.assert_not_called()

    def test_task_creation_is_blocked_by_default(self):
        sync = service(mode="write")
        with self.assertRaisesRegex(RuntimeError, "TODOIST_ALLOW_TASK_CREATE"):
            sync._sync_notion_task(
                {"page_id": "p-1", "title": "Task", "status": "Backlog", "todoist_id": ""},
                {},
                {},
                SyncResult(errors=[]),
            )
        sync.todoist.create_task.assert_not_called()

    def test_unknown_labels_are_preserved(self):
        sync = service(mode="write", allow_label_write=True)
        notion = {
            "todoist_id": "t-1",
            "managed_labels": ["анализ"],
            "todoist_project_id": "",
            "todoist_section_id": "",
        }
        todo = {"id": "t-1", "labels": ["Project A", "custom", "встреча"], "is_completed": False}
        sync._enforce_todoist_routing(notion, todo)
        sync.todoist.update_task_labels.assert_called_once_with("t-1", ["Project A", "custom", "анализ"])

    def test_base_task_update_cannot_bypass_label_and_move_guards(self):
        sync = service(mode="write")
        sync._mark_notion_sync = Mock()
        notion = {
            "page_id": "p-1",
            "todoist_id": "t-1",
            "title": "Changed",
            "description": "",
            "status": "Backlog",
            "managed_labels": ["анализ"],
            "todoist_project_id": "tp-2",
            "todoist_section_id": "s-2",
        }
        todo = {"id": "t-1", "labels": ["custom"], "project_id": "tp-1", "is_completed": False}
        with self.assertRaisesRegex(RuntimeError, "TODOIST_ALLOW_LABEL_WRITE"):
            sync._update_todoist_from_notion(notion, todo)
        payload = sync.todoist.update_task.call_args.args[1]
        self.assertNotIn("managed_labels", payload)
        self.assertNotIn("todoist_project_id", payload)
        self.assertNotIn("todoist_section_id", payload)

    def test_move_is_blocked_without_permission(self):
        sync = service(mode="write")
        notion = {
            "todoist_id": "t-1",
            "managed_labels": [],
            "todoist_project_id": "tp-2",
            "todoist_section_id": "",
        }
        todo = {"id": "t-1", "labels": [], "project_id": "tp-1", "is_completed": False}
        with self.assertRaisesRegex(RuntimeError, "TODOIST_ALLOW_TASK_MOVE"):
            sync._enforce_todoist_routing(notion, todo)
        sync.todoist.update_task_location.assert_not_called()

    def test_move_limit_stops_batch(self):
        sync = service(mode="write", allow_task_move=True, max_task_moves=1)
        notion = {
            "todoist_id": "t-1",
            "managed_labels": [],
            "todoist_project_id": "tp-2",
            "todoist_section_id": "",
        }
        sync._enforce_todoist_routing(notion, {"labels": [], "project_id": "tp-1", "is_completed": False})
        notion["todoist_id"] = "t-2"
        with self.assertRaisesRegex(RuntimeError, "move limit"):
            sync._enforce_todoist_routing(notion, {"labels": [], "project_id": "tp-1", "is_completed": False})

    def test_project_hierarchy_creation_is_isolated_behind_project_write_flag(self):
        todoist = Mock(spec=TodoistClient)
        todoist.enabled = True
        todoist.api_token = "token"
        sync = service(todoist, mode="write", allow_project_create=True)
        sync._set_notion_external_id = Mock()
        sync._set_notion_project_sync = Mock()
        todoist.create_project.side_effect = ["stream-todo", "project-todo"]
        projects = {
            "a": {
                "id": "notion-project",
                "name": "Project A",
                "stream_id": "notion-stream",
                "todoist_project_id": "",
                "sync_enabled": True,
            }
        }
        streams = {
            "business": {
                "id": "notion-stream",
                "name": "Business",
                "todoist_project_id": "",
            }
        }
        sync._ensure_todoist_project_hierarchy(projects, streams, [], SyncResult(errors=[]))
        self.assertEqual(todoist.create_project.call_args_list[0].args, ("Business",))
        self.assertEqual(todoist.create_project.call_args_list[1].args, ("Project A", "stream-todo"))

    def test_project_without_sync_checkbox_is_created_when_project_writes_are_enabled(self):
        sync = service(mode="projects", allow_project_create=True)
        sync._set_notion_project_sync = Mock()
        sync.todoist.create_project.return_value = "todo-project"
        sync._ensure_todoist_project_hierarchy(
            {"a": {"id": "p", "name": "A", "stream_id": "", "todoist_project_id": "", "sync_enabled": False}},
            {},
            [],
            SyncResult(errors=[]),
        )
        sync.todoist.create_project.assert_called_once_with("A", None)

    def test_todoist_primary_creates_new_project_and_fills_notion_sync_fields(self):
        sync = service(mode="todoist-primary")
        sync._set_notion_project_sync = Mock()
        sync.todoist.create_project.return_value = "todo-project"
        sync._ensure_todoist_project_hierarchy(
            {"a": {"id": "p", "name": "A", "stream_id": "", "todoist_project_id": ""}},
            {},
            [],
            SyncResult(errors=[]),
            force=True,
        )
        sync.todoist.create_project.assert_called_once_with("A", None)
        sync._set_notion_project_sync.assert_called_once_with("p", "todo-project")

    def test_todoist_primary_creates_missing_operational_labels_without_editing_tasks(self):
        sync = service(mode="todoist-primary")
        sync.todoist.create_label.side_effect = lambda name: f"id-{name}"
        result = SyncResult(errors=[], mode="todoist-primary")
        sync._ensure_todoist_labels(
            [{"id": "existing", "name": "встреча"}, {"id": "custom", "name": "custom"}],
            result,
        )
        created = {call.args[0] for call in sync.todoist.create_label.call_args_list}
        self.assertEqual(created, MANAGED_TODOIST_LABELS - {"встреча"})
        self.assertEqual(result.labels_created, len(MANAGED_TODOIST_LABELS) - 1)
        sync.todoist.update_task_labels.assert_not_called()

    def test_project_sync_fields_include_id_status_timestamp_and_checkbox(self):
        sync = service(mode="todoist-primary")
        with patch("conductor.task_sync.request_json") as request:
            sync._set_notion_project_sync("page-1", "todo-project")
        properties = request.call_args.kwargs["payload"]["properties"]
        self.assertIn("Todoist Project ID", properties)
        self.assertEqual(properties["Todoist Sync status"], {"select": {"name": "Synced"}})
        self.assertIn("Todoist Last synced", properties)
        self.assertEqual(properties["Синхронизировать с Todoist"], {"checkbox": True})

    def test_rate_limit_retry_after_is_honored(self):
        self.assertEqual(_retry_after(HttpError(429, '{"error_extra":{"retry_after":1280}}')), 1280)


class TodoistClientTest(unittest.TestCase):
    def test_update_task_can_clear_due_date_and_deadline(self):
        client = TodoistClient("token", True)
        with patch("conductor.todoist_client.request_json") as request:
            client.update_task(
                "task-1",
                {"title": "Task", "priority": "P4", "due_date": None, "deadline": None},
            )
        payload = request.call_args.kwargs["payload"]
        self.assertIsNone(payload["due_date"])
        self.assertIsNone(payload["deadline_date"])

    def test_batch_location_update_only_sends_move_commands(self):
        client = TodoistClient("token", True)
        with patch("conductor.todoist_client.request_json") as request:
            request.return_value = {"sync_status": {"command-1": "ok"}}
            with patch("conductor.todoist_client.uuid4", return_value="command-1"):
                failures = client.update_task_locations_batch([("task-1", "project-1")])
        commands = request.call_args.kwargs["payload"]["commands"]
        self.assertEqual(commands, [{"type": "item_move", "uuid": "command-1", "args": {"id": "task-1", "project_id": "project-1"}}])
        self.assertEqual(failures, {})

    def test_move_to_section_does_not_also_send_project(self):
        client = TodoistClient("token", True)
        with patch("conductor.todoist_client.request_json") as request:
            request.return_value = {"sync_status": {"command-1": "ok"}}
            with patch("conductor.todoist_client.uuid4", return_value="command-1"):
                client.update_task_location("task-1", "project-1", "section-1")
        args = request.call_args.kwargs["payload"]["commands"][0]["args"]
        self.assertEqual(args, {"id": "task-1", "section_id": "section-1"})

    def test_create_child_project_sends_parent_id(self):
        client = TodoistClient("token", True)
        with patch("conductor.todoist_client.request_json", return_value={"id": "child"}) as request:
            result = client.create_project("Project A", "stream-1")
        self.assertEqual(result, "child")
        self.assertEqual(request.call_args.kwargs["payload"], {"name": "Project A", "parent_id": "stream-1"})


if __name__ == "__main__":
    unittest.main()
