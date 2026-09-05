import io
import csv
import re
import urllib.request
import json
from typing import List, Optional, Dict, Any
from ..models import Ticket
from .base import TicketSource


class DjangoTracSource(TicketSource):
    def __init__(self, source_id: str = "django", url: str = "https://code.djangoproject.com"):
        super().__init__(source_id)
        self.url = url.rstrip("/")
        self.headers = {"User-Agent": "TicketWatcher/1.0 (+https://github.com/saikat709/ticket-watcher)"}

    def _http_get(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8-sig", errors="replace")

    def _fetch_query_csv(self, max_results: int = 200) -> List[Dict[str, str]]:
        cols = [
            "id", "summary", "type", "status", "priority", "milestone",
            "component", "severity", "resolution", "time", "changetime",
            "reporter", "owner", "stage", "has_patch", "patch_needs_improvement",
            "needs_tests", "needs_docs", "ui_ux", "easy_pickings", "description"
        ]
        col_query = "&".join(f"col={c}" for c in cols)
        query_url = f"{self.url}/query?{col_query}&order=id&desc=1&max={max_results}&format=csv"
        csv_text = self._http_get(query_url)
        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader)

    def _extract_pr_info(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(r"github\.com/django/django/pull/(\d+)", text)
        if match:
            return f"https://github.com/django/django/pull/{match.group(1)}"
        match_any = re.search(r"github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)", text)
        if match_any:
            return f"https://github.com/{match_any.group(1)}/{match_any.group(2)}/pull/{match_any.group(3)}"
        return None

    def _check_pr_status(self, pr_url: str) -> Optional[str]:
        match = re.search(r"github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)", pr_url)
        if not match:
            return None
        owner, repo, pr_num = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
        try:
            req = urllib.request.Request(
                api_url,
                headers={
                    "User-Agent": self.headers["User-Agent"],
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("merged"):
                    return "merged"
                return data.get("state")  # "open" or "closed"
        except Exception:
            return None

    def _row_to_ticket(self, row: Dict[str, str], html_or_rss_text: str = "") -> Ticket:
        ticket_id = int(row["id"])
        summary = row.get("Summary") or row.get("summary") or f"Ticket #{ticket_id}"
        description = row.get("Description") or row.get("description") or ""
        status = row.get("Status") or row.get("status") or "new"
        resolution = row.get("Resolution") or row.get("resolution") or ""
        reporter = row.get("Reporter") or row.get("reporter") or ""
        owner = row.get("Owner") or row.get("owner") or ""
        component = row.get("Component") or row.get("component") or ""
        priority = row.get("Severity") or row.get("Priority") or row.get("priority") or "Normal"
        severity = row.get("Severity") or row.get("severity") or ""
        stage = row.get("Triage Stage") or row.get("stage") or ""

        created_at = row.get("Created") or row.get("time") or ""
        updated_at = row.get("Modified") or row.get("changetime") or ""

        labels = []
        if stage:
            labels.append(stage)
        if row.get("Has patch") == "1":
            labels.append("has-patch")
        if row.get("Patch needs improvement") == "1":
            labels.append("patch-needs-improvement")
        if row.get("Needs tests") == "1":
            labels.append("needs-tests")
        if row.get("Needs documentation") == "1":
            labels.append("needs-docs")
        if row.get("UI/UX") == "1":
            labels.append("ui/ux")
        if row.get("Easy pickings") == "1":
            labels.append("easy-pickings")

        ticket_url = f"{self.url}/ticket/{ticket_id}"
        combined_text = f"{description}\n{html_or_rss_text}"
        pr_url = self._extract_pr_info(combined_text)
        pr_status = self._check_pr_status(pr_url) if pr_url else None

        return Ticket(
            id=ticket_id,
            source_id=self.source_id,
            title=summary,
            description=description,
            status=status,
            resolution=resolution,
            created_at=created_at,
            updated_at=updated_at,
            reporter=reporter,
            owner=owner,
            component=component,
            priority=priority,
            severity=severity,
            triage_stage=stage,
            labels=labels,
            url=ticket_url,
            pr_url=pr_url,
            pr_status=pr_status,
            raw_data=dict(row),
        )

    def fetch_new_tickets(self, last_seen_id: int) -> List[Ticket]:
        rows = self._fetch_query_csv(max_results=200)
        new_rows = []
        for r in rows:
            try:
                tid = int(r["id"])
                if tid > last_seen_id:
                    new_rows.append((tid, r))
            except (ValueError, KeyError):
                continue

        # Sort ascending by ticket ID
        new_rows.sort(key=lambda x: x[0])

        tickets = []
        for tid, r in new_rows:
            # Fetch ticket RSS to check for PR links in comments if description doesn't have it
            rss_text = ""
            try:
                rss_url = f"{self.url}/ticket/{tid}?format=rss"
                rss_text = self._http_get(rss_url)
            except Exception:
                pass
            tickets.append(self._row_to_ticket(r, rss_text))

        return tickets

    def fetch_ticket(self, ticket_id: int) -> Optional[Ticket]:
        rows = self._fetch_query_csv(max_results=300)
        row = None
        for r in rows:
            if r.get("id") == str(ticket_id):
                row = r
                break

        rss_text = ""
        try:
            rss_url = f"{self.url}/ticket/{ticket_id}?format=rss"
            rss_text = self._http_get(rss_url)
        except Exception:
            pass

        if row:
            return self._row_to_ticket(row, rss_text)

        # Fallback if not found in query
        ticket_url = f"{self.url}/ticket/{ticket_id}"
        pr_url = self._extract_pr_info(rss_text)
        pr_status = self._check_pr_status(pr_url) if pr_url else None
        return Ticket(
            id=ticket_id,
            source_id=self.source_id,
            title=f"Ticket #{ticket_id}",
            description="",
            status="unknown",
            url=ticket_url,
            pr_url=pr_url,
            pr_status=pr_status,
            raw_data={"id": str(ticket_id)},
        )

    def detect_changes(self, old_ticket: Ticket, new_ticket: Ticket) -> List[str]:
        changes = []
        if old_ticket.status != new_ticket.status:
            changes.append(f"Status: {old_ticket.status} → {new_ticket.status}")
        if old_ticket.resolution != new_ticket.resolution:
            changes.append(f"Resolution: '{old_ticket.resolution}' → '{new_ticket.resolution}'")
        if old_ticket.owner != new_ticket.owner:
            old_owner = old_ticket.owner or "unassigned"
            new_owner = new_ticket.owner or "unassigned"
            changes.append(f"Owner: {old_owner} → {new_owner}")
        if old_ticket.component != new_ticket.component:
            changes.append(f"Component: {old_ticket.component} → {new_ticket.component}")
        if old_ticket.triage_stage != new_ticket.triage_stage:
            changes.append(f"Triage Stage: {old_ticket.triage_stage} → {new_ticket.triage_stage}")

        if old_ticket.pr_url != new_ticket.pr_url:
            if new_ticket.pr_url:
                changes.append(f"Pull Request linked: {new_ticket.pr_url}")
            else:
                changes.append(f"Pull Request unlinked: {old_ticket.pr_url}")
        elif old_ticket.pr_status != new_ticket.pr_status and new_ticket.pr_status:
            changes.append(f"PR Status: {old_ticket.pr_status} → {new_ticket.pr_status}")

        added_labels = set(new_ticket.labels) - set(old_ticket.labels)
        if added_labels:
            changes.append(f"Added label(s): {', '.join(sorted(added_labels))}")
        removed_labels = set(old_ticket.labels) - set(new_ticket.labels)
        if removed_labels:
            changes.append(f"Removed label(s): {', '.join(sorted(removed_labels))}")

        return changes

    def is_completed(self, ticket: Ticket) -> bool:
        if ticket.pr_status == "merged":
            return True
        st = ticket.status.lower()
        res = ticket.resolution.lower()
        if st in ["closed", "resolved"]:
            return True
        return False
