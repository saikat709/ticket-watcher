from typing import List, Optional
from ..models import Ticket


def format_initial_notification_comment(user: str) -> str:
    username = user.lstrip("@")
    return f"@{username} — New ticket detected. Please check this out."


def format_update_comment(ticket: Ticket, changes: List[str]) -> str:
    lines = ["**Ticket update detected:**", ""]
    for c in changes:
        lines.append(f"- {c}")
    return "\n".join(lines)


def format_completion_comment(ticket: Ticket, details: Optional[str] = None) -> str:
    lines = ["✅ **Completed**", ""]
    if details:
        lines.append(details)
    elif ticket.pr_url and ticket.pr_status == "merged":
        lines.append(f"Pull Request {ticket.pr_url} was merged.")
    elif ticket.resolution:
        lines.append(f"Ticket #{ticket.id} was resolved as `{ticket.resolution}`.")
    else:
        lines.append(f"Ticket #{ticket.id} work is complete.")

    lines.append("")
    lines.append("This ticket is no longer actively tracked.")
    return "\n".join(lines)
