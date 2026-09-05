import json
import urllib.request
from typing import List, Optional, Dict, Any
from ..models import Ticket
from .base import TicketSource


class GitHubSource(TicketSource):
    def __init__(self, source_id: str, repository: str):
        super().__init__(source_id)
        self.repository = repository
        self.headers = {
            "User-Agent": "TicketWatcher/1.0 (+https://github.com/saikat709/ticket-watcher)",
            "Accept": "application/vnd.github.v3+json",
        }

    def _http_get_json(self, url: str) -> Any:
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch_new_tickets(self, last_seen_id: int) -> List[Ticket]:
        url = f"https://api.github.com/repos/{self.repository}/issues?state=all&sort=created&direction=asc&per_page=100"
        try:
            items = self._http_get_json(url)
        except Exception:
            return []

        tickets = []
        for item in items:
            if "pull_request" in item:
                continue
            issue_num = int(item["number"])
            if issue_num > last_seen_id:
                t = self._item_to_ticket(item)
                tickets.append(t)

        tickets.sort(key=lambda x: x.id)
        return tickets

    def fetch_ticket(self, ticket_id: int) -> Optional[Ticket]:
        url = f"https://api.github.com/repos/{self.repository}/issues/{ticket_id}"
        try:
            item = self._http_get_json(url)
            return self._item_to_ticket(item)
        except Exception:
            return None

    def _item_to_ticket(self, item: Dict[str, Any]) -> Ticket:
        ticket_id = int(item["number"])
        title = item.get("title", "")
        body = item.get("body", "") or ""
        state = item.get("state", "open")
        labels = [l["name"] for l in item.get("labels", []) if isinstance(l, dict) and "name" in l]

        pr_url = item.get("pull_request", {}).get("html_url") if isinstance(item.get("pull_request"), dict) else None

        return Ticket(
            id=ticket_id,
            source_id=self.source_id,
            title=title,
            description=body,
            status=state,
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            reporter=item.get("user", {}).get("login", "") if isinstance(item.get("user"), dict) else "",
            owner=item.get("assignee", {}).get("login", "") if isinstance(item.get("assignee"), dict) else "",
            labels=labels,
            url=item.get("html_url", f"https://github.com/{self.repository}/issues/{ticket_id}"),
            pr_url=pr_url,
            raw_data=item,
        )

    def detect_changes(self, old_ticket: Ticket, new_ticket: Ticket) -> List[str]:
        changes = []
        if old_ticket.status != new_ticket.status:
            changes.append(f"Status: {old_ticket.status} → {new_ticket.status}")
        if old_ticket.owner != new_ticket.owner:
            changes.append(f"Assignee: {old_ticket.owner or 'none'} → {new_ticket.owner or 'none'}")
        added = set(new_ticket.labels) - set(old_ticket.labels)
        if added:
            changes.append(f"Added label(s): {', '.join(sorted(added))}")
        return changes

    def is_completed(self, ticket: Ticket) -> bool:
        return ticket.status.lower() == "closed"
