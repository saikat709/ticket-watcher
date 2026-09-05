import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from watcher.models import Ticket
from watcher.state import StateManager
from watcher.main import run_update


class TestTracking(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.yaml"
        self.state_path = Path(self.temp_dir.name) / "state.json"

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
    def test_tracking_no_changes(self, mock_gh_cls, mock_source_cls):
        t_dict = {
            "id": 37351,
            "source_id": "django",
            "title": "Fix ORM issue",
            "status": "new",
            "owner": "",
            "component": "ORM",
            "pr_url": None,
            "pr_status": None,
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({
                "sources": {"django": {"last_seen_id": 37351}},
                "tracked": {
                    "django:37351": {
                        "source": "django",
                        "ticket_id": 37351,
                        "watcher_issue_number": 15,
                        "status": "new",
                        "last_checked": "2026-09-05T00:00:00Z",
                        "ticket_data": t_dict,
                    }
                }
            }, f)

        mock_source = MagicMock()
        mock_source_cls.return_value = mock_source
        current_t = Ticket.from_dict(t_dict)
        mock_source.fetch_ticket.return_value = current_t
        mock_source.detect_changes.return_value = []
        mock_source.is_completed.return_value = False

        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh

        run_update(str(self.config_path), str(self.state_path))

        # No GitHub update API calls made when unchanged
        mock_gh.update_issue.assert_not_called()
        mock_gh.create_comment.assert_not_called()

        # State remains tracked
        sm = StateManager(str(self.state_path))
        self.assertIsNotNone(sm.get_tracked_entry("django:37351"))

    @patch("watcher.main.DjangoTracSource")
    @patch("watcher.main.GitHubClient")
    def test_tracking_meaningful_changes(self, mock_gh_cls, mock_source_cls):
        old_dict = {
            "id": 37351,
            "source_id": "django",
            "title": "Fix ORM issue",
            "status": "new",
            "owner": "",
            "component": "ORM",
            "pr_url": None,
            "pr_status": None,
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({
                "sources": {"django": {"last_seen_id": 37351}},
                "tracked": {
                    "django:37351": {
                        "source": "django",
                        "ticket_id": 37351,
                        "watcher_issue_number": 15,
                        "status": "new",
                        "last_checked": "2026-09-05T00:00:00Z",
                        "ticket_data": old_dict,
                    }
                }
            }, f)

        mock_source = MagicMock()
        mock_source_cls.return_value = mock_source
        current_t = Ticket(
            id=37351,
            source_id="django",
            title="Fix ORM issue",
            description="",
            status="assigned",
            owner="developer_alex",
            component="ORM",
            pr_url="https://github.com/django/django/pull/21890",
            pr_status="open",
        )
        mock_source.fetch_ticket.return_value = current_t
        mock_source.detect_changes.return_value = [
            "Status: new → assigned",
            "Owner: unassigned → developer_alex",
            "Pull Request linked: https://github.com/django/django/pull/21890",
        ]
        mock_source.is_completed.return_value = False

        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh

        run_update(str(self.config_path), str(self.state_path))

        # Check GitHub update issue & comment calls
        mock_gh.update_issue.assert_called_once()
        mock_gh.create_comment.assert_called_once()
        comment_body = mock_gh.create_comment.call_args[1]["body"]
        self.assertIn("Status: new → assigned", comment_body)
        self.assertIn("Pull Request linked", comment_body)


if __name__ == "__main__":
    unittest.main()
