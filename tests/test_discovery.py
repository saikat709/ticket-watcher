import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from watcher.models import Ticket, WatcherConfig, SourceConfig
from watcher.state import StateManager
from watcher.main import run_discovery


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.yaml"
        self.state_path = Path(self.temp_dir.name) / "state.json"

        # Setup mock config
        config_content = """
watcher_repository: "saikat709/ticket-watcher"
notification_user: "saikat709"
sources:
  - id: "django"
    type: "django_trac"
    url: "https://code.djangoproject.com"
"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(config_content)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("watcher.main.DjangoTracSource")
    @patch("watcher.main.GitHubClient")
    def test_new_ticket_detection_and_processing(self, mock_gh_cls, mock_source_cls):
        # Initial state with manual baseline last_seen_id = 37350
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"sources": {"django": {"last_seen_id": 37350}}, "tracked": {}}, f)

        mock_source = MagicMock()
        mock_source_cls.return_value = mock_source

        # Discovered 2 new tickets: #37351 and #37352
        t1 = Ticket(id=37351, source_id="django", title="New feature A", description="Desc A", status="new")
        t2 = Ticket(id=37352, source_id="django", title="Bug fix B", description="Desc B", status="new")
        mock_source.fetch_new_tickets.return_value = [t1, t2]

        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh
        mock_gh.search_issue.return_value = None  # No existing issue
        mock_gh.create_issue.side_effect = [{"number": 101}, {"number": 102}]

        run_discovery(str(self.config_path), str(self.state_path))

        # Check GitHub issue creation calls
        self.assertEqual(mock_gh.create_issue.call_count, 2)
        self.assertEqual(mock_gh.create_comment.call_count, 2)

        # Check comment mentions user
        first_comment_args = mock_gh.create_comment.call_args_list[0][1]
        self.assertIn("@saikat709", first_comment_args["body"])

        # Verify state updated
        sm = StateManager(str(self.state_path))
        self.assertEqual(sm.get_last_seen_id("django"), 37352)
        self.assertIsNotNone(sm.get_tracked_entry("django:37351"))
        self.assertIsNotNone(sm.get_tracked_entry("django:37352"))

    @patch("watcher.main.DjangoTracSource")
    @patch("watcher.main.GitHubClient")
    def test_duplicate_prevention(self, mock_gh_cls, mock_source_cls):
        # State already tracks django:37351 with issue #101 but comment creation had failed earlier
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({
                "sources": {"django": {"last_seen_id": 37350}},
                "tracked": {
                    "django:37351": {
                        "source": "django",
                        "ticket_id": 37351,
                        "watcher_issue_number": 101,
                        "status": "new",
                        "notification_comment_created": False,
                        "ticket_data": {"id": 37351, "source_id": "django", "title": "Test", "description": "", "status": "new"}
                    }
                }
            }, f)

        mock_source = MagicMock()
        mock_source_cls.return_value = mock_source
        t1 = Ticket(id=37351, source_id="django", title="Test", description="", status="new")
        mock_source.fetch_new_tickets.return_value = [t1]

        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh

        run_discovery(str(self.config_path), str(self.state_path))

        # create_issue MUST NOT be called because tracked entry has issue #101
        mock_gh.create_issue.assert_not_called()

        # create_comment MUST be called to retry notification comment
        mock_gh.create_comment.assert_called_once_with(
            repo="saikat709/ticket-watcher",
            issue_number=101,
            body="@saikat709 — New ticket detected. Please check this out."
        )

        sm = StateManager(str(self.state_path))
        self.assertTrue(sm.get_tracked_entry("django:37351")["notification_comment_created"])

    @patch("watcher.main.DjangoTracSource")
    @patch("watcher.main.GitHubClient")
    def test_recovery_after_issue_creation_failure(self, mock_gh_cls, mock_source_cls):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"sources": {"django": {"last_seen_id": 37350}}, "tracked": {}}, f)

        mock_source = MagicMock()
        mock_source_cls.return_value = mock_source
        t1 = Ticket(id=37351, source_id="django", title="Fail Ticket", description="", status="new")
        mock_source.fetch_new_tickets.return_value = [t1]

        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh
        mock_gh.search_issue.return_value = None
        mock_gh.create_issue.side_effect = RuntimeError("Network timeout")

        run_discovery(str(self.config_path), str(self.state_path))

        # last_seen_id must NOT advance if issue creation failed!
        sm = StateManager(str(self.state_path))
        self.assertEqual(sm.get_last_seen_id("django"), 37350)
        self.assertNotIn("django:37351", sm.get_all_tracked())


if __name__ == "__main__":
    unittest.main()
