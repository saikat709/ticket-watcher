import json
import tempfile
import unittest
from pathlib import Path

from watcher.state import StateManager


class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_state_loading_missing_file(self):
        sm = StateManager(str(self.state_path))
        self.assertEqual(sm.data, {"sources": {}, "tracked": {}})
        self.assertIsNone(sm.get_last_seen_id("django"))

    def test_manual_initial_last_seen_id(self):
        initial_content = {
            "sources": {
                "django": {
                    "last_seen_id": 37350
                }
            },
            "tracked": {}
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(initial_content, f)

        sm = StateManager(str(self.state_path))
        self.assertEqual(sm.get_last_seen_id("django"), 37350)
        self.assertEqual(sm.get_all_tracked(), {})

    def test_state_saving_and_persistence(self):
        sm = StateManager(str(self.state_path))
        sm.set_last_seen_id("django", 37351)
        sm.add_or_update_tracked(
            key="django:37351",
            source_id="django",
            ticket_id=37351,
            watcher_issue_number=15,
            ticket_data={"title": "Test Ticket"},
            status="new",
        )
        sm.save()

        # Reload from disk
        sm2 = StateManager(str(self.state_path))
        self.assertEqual(sm2.get_last_seen_id("django"), 37351)
        entry = sm2.get_tracked_entry("django:37351")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["watcher_issue_number"], 15)

    def test_remove_tracked_keeps_last_seen_id(self):
        sm = StateManager(str(self.state_path))
        sm.set_last_seen_id("django", 37351)
        sm.add_or_update_tracked(
            key="django:37351",
            source_id="django",
            ticket_id=37351,
            watcher_issue_number=15,
            ticket_data={"title": "Test Ticket"},
            status="new",
        )
        sm.save()

        # Remove tracked ticket
        removed = sm.remove_tracked("django:37351")
        self.assertTrue(removed)
        sm.save()

        # Verify tracked is empty but last_seen_id remains intact
        sm2 = StateManager(str(self.state_path))
        self.assertEqual(sm2.get_all_tracked(), {})
        self.assertEqual(sm2.get_last_seen_id("django"), 37351)


if __name__ == "__main__":
    unittest.main()
