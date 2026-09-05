import sys
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .config import load_config
from .state import StateManager
from .models import Ticket, WatcherConfig
from .sources import TicketSource, DjangoTracSource, GitHubSource
from .github import (
    GitHubClient,
    format_issue_title,
    format_issue_body,
    format_updated_issue_body,
    format_initial_notification_comment,
    format_update_comment,
    format_completion_comment,
)


def get_source_handler(source_cfg: Any) -> TicketSource:
    stype = source_cfg.type.lower()
    if stype == "django_trac":
        return DjangoTracSource(source_id=source_cfg.id, url=source_cfg.url or "https://code.djangoproject.com")
    elif stype == "github":
        return GitHubSource(source_id=source_cfg.id, repository=source_cfg.repository or "")
    else:
        raise ValueError(f"Unsupported source type: {source_cfg.type}")


def run_discovery(config_path: str, state_path: str, dry_run: bool = False) -> None:
    config = load_config(config_path)
    state = StateManager(state_path)
    client = GitHubClient() if not dry_run else None

    print(f"Starting discovery job for {len(config.sources)} source(s)...")

    for s_cfg in config.sources:
        last_seen_id = state.get_last_seen_id(s_cfg.id)
        if last_seen_id is None:
            print(
                f"WARNING: Source '{s_cfg.id}' has no configured 'last_seen_id' in state.json. "
                f"Please manually set the initial baseline 'last_seen_id' in state.json before running discovery."
            )
            continue

        handler = get_source_handler(s_cfg)
        print(f"Fetching new tickets for '{s_cfg.id}' (last_seen_id={last_seen_id})...")

        try:
            new_tickets = handler.fetch_new_tickets(last_seen_id)
        except Exception as e:
            print(f"ERROR: Failed to fetch new tickets for source '{s_cfg.id}': {e}")
            continue

        print(f"Discovered {len(new_tickets)} new ticket(s) for '{s_cfg.id}'.")

        for ticket in new_tickets:
            key = ticket.key
            print(f"\nProcessing new ticket {key}: '{ticket.title}'...")

            tracked_entry = state.get_tracked_entry(key)
            issue_number = tracked_entry.get("watcher_issue_number") if tracked_entry else None
            comment_created = tracked_entry.get("notification_comment_created", False) if tracked_entry else False

            issue_title = format_issue_title(ticket)
            now_iso = datetime.now(timezone.utc).isoformat()
            issue_body = format_issue_body(ticket, now_iso)

            # 1. Create or resolve watcher issue
            if not issue_number and client:
                # Check idempotency / existing issue on GitHub before creating
                existing_issue_num = client.search_issue(config.watcher_repository, issue_title)
                if existing_issue_num:
                    print(f"Found existing watcher Issue #{existing_issue_num} on GitHub for {key}.")
                    issue_number = existing_issue_num
                else:
                    try:
                        res = client.create_issue(
                            repo=config.watcher_repository,
                            title=issue_title,
                            body=issue_body,
                            labels=ticket.labels,
                        )
                        issue_number = int(res["number"])
                        print(f"Created watcher Issue #{issue_number} for {key}.")
                    except Exception as e:
                        print(f"ERROR: Failed to create watcher Issue for {key}: {e}")
                        # Do NOT advance last_seen_id if Issue creation failed completely
                        continue
            elif not issue_number and dry_run:
                issue_number = 999
                print(f"[DRY RUN] Would create watcher Issue for {key}.")

            # Save state immediately with issue_number to prevent recreation on retries
            state.add_or_update_tracked(
                key=key,
                source_id=s_cfg.id,
                ticket_id=ticket.id,
                watcher_issue_number=issue_number,
                ticket_data=ticket.to_dict(),
                status=ticket.status,
                notification_comment_created=comment_created,
                last_checked=now_iso,
                last_updated=now_iso,
            )
            state.save()

            # 2. Create notification comment if needed
            if not comment_created and issue_number and config.notification_user:
                comment_text = format_initial_notification_comment(config.notification_user)
                if client:
                    try:
                        client.create_comment(
                            repo=config.watcher_repository,
                            issue_number=issue_number,
                            body=comment_text,
                        )
                        print(f"Created notification comment on Issue #{issue_number} for @{config.notification_user}.")
                        comment_created = True
                        state.add_or_update_tracked(
                            key=key,
                            source_id=s_cfg.id,
                            ticket_id=ticket.id,
                            watcher_issue_number=issue_number,
                            ticket_data=ticket.to_dict(),
                            status=ticket.status,
                            notification_comment_created=True,
                            last_checked=now_iso,
                            last_updated=now_iso,
                        )
                        state.save()
                    except Exception as e:
                        print(f"ERROR: Failed to create notification comment on Issue #{issue_number}: {e}")
                elif dry_run:
                    print(f"[DRY RUN] Would create notification comment for @{config.notification_user}.")
                    comment_created = True

            # 3. Advance source last_seen_id after successful ticket processing
            state.set_last_seen_id(s_cfg.id, ticket.id)
            state.save()
            print(f"Updated last_seen_id for source '{s_cfg.id}' to {ticket.id}.")

    print("Discovery job completed.")


def run_update(config_path: str, state_path: str, dry_run: bool = False) -> None:
    config = load_config(config_path)
    state = StateManager(state_path)
    client = GitHubClient() if not dry_run else None

    tracked = state.get_all_tracked()
    print(f"Starting 24-hour tracking job for {len(tracked)} active ticket(s)...")

    # Create handler cache per source
    handlers: Dict[str, TicketSource] = {}
    for s_cfg in config.sources:
        try:
            handlers[s_cfg.id] = get_source_handler(s_cfg)
        except Exception as e:
            print(f"WARNING: Could not initialize handler for source '{s_cfg.id}': {e}")

    keys_to_process = list(tracked.keys())
    now_iso = datetime.now(timezone.utc).isoformat()

    for key in keys_to_process:
        entry = tracked.get(key)
        if not entry:
            continue

        source_id = entry["source"]
        ticket_id = int(entry["ticket_id"])
        issue_number = int(entry["watcher_issue_number"])
        old_ticket_dict = entry.get("ticket_data", {})
        old_ticket = Ticket.from_dict(old_ticket_dict) if old_ticket_dict else Ticket(id=ticket_id, source_id=source_id, title="", description="", status="")

        handler = handlers.get(source_id)
        if not handler:
            # Fallback handler lookup
            s_cfg = next((s for s in config.sources if s.id == source_id), None)
            if s_cfg:
                handler = get_source_handler(s_cfg)
                handlers[source_id] = handler

        if not handler:
            print(f"Skipping {key}: No source handler configured.")
            continue

        print(f"\nChecking active ticket {key} (Watcher Issue #{issue_number})...")
        try:
            current_ticket = handler.fetch_ticket(ticket_id)
        except Exception as e:
            print(f"ERROR: Failed to fetch current state for {key}: {e}")
            continue

        if not current_ticket:
            print(f"WARNING: Could not fetch ticket details for {key}.")
            continue

        changes = handler.detect_changes(old_ticket, current_ticket)
        completed = handler.is_completed(current_ticket)

        if completed:
            print(f"Ticket {key} is COMPLETED (resolution='{current_ticket.resolution}', status='{current_ticket.status}', PR status='{current_ticket.pr_status}').")
            updated_body = format_updated_issue_body(current_ticket, changes, now_iso, completed=True)
            comp_comment = format_completion_comment(current_ticket)

            if client:
                try:
                    client.update_issue(config.watcher_repository, issue_number, body=updated_body)
                    client.create_comment(config.watcher_repository, issue_number, body=comp_comment)
                    print(f"Updated Issue #{issue_number} and posted completion comment.")
                except Exception as e:
                    print(f"ERROR: Failed to update GitHub Issue #{issue_number} on completion: {e}")

            # Remove ticket from tracked, keeping permanent last_seen_id
            state.remove_tracked(key)
            state.save()
            print(f"Removed {key} from tracked state.")

        elif changes:
            print(f"Detected {len(changes)} change(s) for {key}: {changes}")
            updated_body = format_updated_issue_body(current_ticket, changes, now_iso, completed=False)
            upd_comment = format_update_comment(current_ticket, changes)

            if client:
                try:
                    client.update_issue(config.watcher_repository, issue_number, body=updated_body)
                    client.create_comment(config.watcher_repository, issue_number, body=upd_comment)
                    print(f"Updated Issue #{issue_number} and posted update comment.")
                except Exception as e:
                    print(f"ERROR: Failed to update GitHub Issue #{issue_number} for {key}: {e}")

            state.add_or_update_tracked(
                key=key,
                source_id=source_id,
                ticket_id=ticket_id,
                watcher_issue_number=issue_number,
                ticket_data=current_ticket.to_dict(),
                status=current_ticket.status,
                notification_comment_created=entry.get("notification_comment_created", True),
                last_checked=now_iso,
                last_updated=now_iso,
            )
            state.save()

        else:
            print(f"No meaningful changes detected for {key}.")
            state.add_or_update_tracked(
                key=key,
                source_id=source_id,
                ticket_id=ticket_id,
                watcher_issue_number=issue_number,
                ticket_data=current_ticket.to_dict(),
                status=current_ticket.status,
                notification_comment_created=entry.get("notification_comment_created", True),
                last_checked=now_iso,
                last_updated=entry.get("last_updated"),
            )
            state.save()

    print("Tracking job completed.")


def main():
    parser = argparse.ArgumentParser(description="Open-Source Ticket Watcher")
    parser.add_argument("command", choices=["discover", "update"], help="Command to run: 'discover' or 'update'")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--state", default="state.json", help="Path to state.json (default: state.json)")
    parser.add_argument("--dry-run", action="store_true", help="Run without posting to GitHub API")

    args = parser.parse_args()

    if args.command == "discover":
        run_discovery(args.config, args.state, args.dry_run)
    elif args.command == "update":
        run_update(args.config, args.state, args.dry_run)


if __name__ == "__main__":
    main()
