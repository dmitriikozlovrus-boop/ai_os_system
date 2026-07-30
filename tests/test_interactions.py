import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory

from conductor.interactions import InteractionStore


class InteractionStoreTest(unittest.TestCase):
    def test_corrupt_json_does_not_break_store(self):
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "interactions.json")
            with open(path, "w", encoding="utf-8") as file:
                file.write("{broken")
            store = InteractionStore(path)

            self.assertIsNone(store.latest_for_chat(42))
            created = store.create(42, text="Нужен ноутбук", model="m")

            self.assertEqual(store.latest_for_chat(42, completed_only=False)["interaction_id"], created)

    def test_service_keys_do_not_mix_with_latest_interaction(self):
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "interactions.json")
            stale = {
                "_feedback": {"42": {"state": "awaiting_correction", "timestamp": datetime.now(timezone.utc).isoformat()}},
                "_issue_fingerprints": {"fp": datetime.now(timezone.utc).isoformat()},
            }
            with open(path, "w", encoding="utf-8") as file:
                json.dump(stale, file)
            store = InteractionStore(path)

            self.assertIsNone(store.latest_for_chat(42))

    def test_expired_feedback_state_is_ignored(self):
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "interactions.json")
            expired = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            with open(path, "w", encoding="utf-8") as file:
                json.dump({"_feedback": {"42": {"state": "awaiting_correction", "timestamp": expired}}}, file)
            store = InteractionStore(path)

            self.assertIsNone(store.get_feedback(42))

    def test_fingerprint_ttl_allows_later_automatic_issue(self):
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "interactions.json")
            expired = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            with open(path, "w", encoding="utf-8") as file:
                json.dump({"_issue_fingerprints": {"fp": expired}}, file)
            store = InteractionStore(path)

            self.assertFalse(store.has_issue_fingerprint("fp"))


if __name__ == "__main__":
    unittest.main()
