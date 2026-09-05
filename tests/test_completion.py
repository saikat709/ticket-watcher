import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from watcher.models import Ticket
from watcher.state import StateManager
from watcher.main import run_update


class TestCompletion(unittest.TestCase):
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
    def test_pr_merged_completion_lifecycle(self, mock_gh_cls, mock_source_cls):
        t_dict = {
            "id": 37351,
            "source_id": "django",
            "title": "Fix ORM issue",
            "status": "assigned",
            "pr_url": "https://github.com/django/django/pull/21890",
            "pr_status": "open",
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({
                "sources": {"django": {"last_seen_id": 37351}},
                "tracked": {
                    "django:37351": {
                        "source": "django",
                        "ticket_id": 37351,
                        "watcher_issue_number": 15,
                        "status": "assigned",
                        "last_checked": "2026-09-05T00:00:00Z",
                        "ticket_data": t_dict,
                    }
                }
            }, f)

        mock_source = MagicMock()
        mock_source_cls.return_value = mock_source
        completed_t = Ticket(
            id=37351,
            source_id="django",
            title="Fix ORM issue",
            description="",
            status="closed",
            resolution="fixed",
            pr_url="https://github.com/django/django/pull/21890",
            pr_status="merged",
        )
        mock_source.fetch_ticket.return_value = completed_t
        mock_source.detect_changes.return_value = ["PR Status: open → merged", "Status: assigned → closed"]
        mock_source.is_completed.return_value = True

        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh

        run_update(str(self.config_path), str(self.state_path))

        # Check issue update and completion comment posted
        mock_gh.update_issue.assert_called_once()
        mock_gh.create_comment.assert_called_once()
        comment_body = mock_gh.create_comment.call_args[1]["body"]
        self.assertIn("✅ **Completed**", comment_body)
        self.assertIn("no longer actively tracked", comment_body)

        # Check state: ticket removed from tracked, but last_seen_id remains intact!
        sm = StateManager(str(self.state_path))
        self.assertEqual(sm.get_all_tracked(), {})
        self.assertEqual(sm.get_last_seen_id("django"), 37351)


if __name__ == "__main__":
    unittest.main()
