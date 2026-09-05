from typing import List, Optional
from ..models import Ticket


def format_source_display_name(source_id: str) -> str:
    mapping = {
        "django": "Django",
        "pylint": "Pylint",
        "metacall": "MetaCall",
    }
    return mapping.get(source_id.lower(), source_id.capitalize())


def format_issue_title(ticket: Ticket) -> str:
    source_display = format_source_display_name(ticket.source_id)
    return f"[{source_display} #{ticket.id}] {ticket.title}"


def format_issue_body(ticket: Ticket, last_checked_iso: str) -> str:
    source_display = format_source_display_name(ticket.source_id)
    labels_str = ", ".join(ticket.labels) if ticket.labels else "None"
    pr_str = "None"
    if ticket.pr_url:
        status_suffix = f" ({ticket.pr_status})" if ticket.pr_status else ""
        pr_str = f"{ticket.pr_url}{status_suffix}"

    desc = ticket.description.strip() if ticket.description else "No description provided."

    lines = [
        f"**Source:** {source_display}",
        "",
        f"**Ticket:** #{ticket.id}",
        f"**Status:** {ticket.status.capitalize()}",
        f"**Resolution:** {ticket.resolution or 'None'}",
        f"**Created:** {ticket.created_at or 'Unknown'}",
        f"**Component:** {ticket.component or 'N/A'}",
        f"**Priority:** {ticket.priority or 'Normal'}",
        f"**Owner:** {ticket.owner or 'unassigned'}",
        f"**Reporter:** {ticket.reporter or 'Unknown'}",
        f"**Triage Stage:** {ticket.triage_stage or 'N/A'}",
        "",
        "### Description",
        desc,
        "",
        f"**Labels:** {labels_str}",
        f"**Pull Request:** {pr_str}",
        "",
        f"**Original ticket:** [#{ticket.id}]({ticket.url})",
        "",
        f"**Last checked:** {last_checked_iso}",
    ]
    return "\n".join(lines)


def format_updated_issue_body(
    ticket: Ticket,
    recent_changes: List[str],
    last_checked_iso: str,
    completed: bool = False,
) -> str:
    base_body = format_issue_body(ticket, last_checked_iso)
    if not recent_changes and not completed:
        return base_body

    lines = [base_body, "", "### Tracking Activity History"]
    if recent_changes:
        for c in recent_changes:
            lines.append(f"- [{last_checked_iso[:10]}] {c}")
    if completed:
        lines.append(f"- [{last_checked_iso[:10]}] ✅ **Completed** (Work finished / PR merged / Ticket resolved)")

    return "\n".join(lines)
