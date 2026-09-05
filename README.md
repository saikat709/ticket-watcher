# Open-Source Ticket Watcher

A stateful Python application and GitHub Actions system designed to monitor open-source issue trackers (starting with **Django Trac** and extensible to **GitHub repositories** and other issue trackers).

Whenever a new ticket appears on a monitored issue tracker, Ticket Watcher creates an Issue in your personal watcher repository and notifies you via a separate `@mention` comment (`@saikat709`). It continuously tracks active tickets every 24 hours for meaningful changes (status changes, owner/assignee changes, triage stage updates, patch flags, pull requests, and PR merges) and automatically stops tracking them once work is completed.

---

## High-Level Architecture

The system consists of two independent, automated jobs powered by **GitHub Actions** using a single JSON file (`state.json`) as machine state and **GitHub Issues** as human-readable history.

```text
               ┌────────────────────────────────────────┐
               │           Source Tracker               │
               │   (Django Trac / GitHub Repositories)  │
               └───────────────────┬────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│ Discovery Job                 │           │ 24-Hour Tracking Job          │
│ (Runs every 30 mins)          │           │ (Runs once daily)             │
├───────────────────────────────┤           ├───────────────────────────────┤
│ 1. Read state.json            │           │ 1. Read tracked tickets       │
│ 2. Fetch new tickets          │           │ 2. Fetch current ticket state │
│ 3. Detect tickets > baseline  │           │ 3. Compare against prev state │
│ 4. Create watcher Issue       │           │ 4. Detect changes / PR merge  │
│ 5. Post @saikat709 comment    │           │ 5. Update existing Issue      │
│ 6. Add to tracked state       │           │ 6. If completed: remove from  │
│ 7. Advance last_seen_id       │           │    tracked (keep cursor)      │
│ 8. Commit state.json          │           │ 7. Commit state.json          │
└───────────────────────────────┘           └───────────────────────────────┘
```

---

## VERY IMPORTANT: Initial State Configuration

> [!IMPORTANT]
> **Initial `last_seen_id` is NOT automatically discovered!**
> You MUST manually inspect the source issue tracker and set the baseline ticket ID in `state.json` BEFORE enabling scheduled discovery.

### Manual Initial Setup Steps

1. Visit [Django Trac](https://code.djangoproject.com/) (or the target issue tracker) to find the current latest ticket ID.
2. If the current latest Django ticket is `#37350`, update `state.json` to:

```json
{
  "sources": {
    "django": {
      "last_seen_id": 37350
    }
  },
  "tracked": {}
}
```

3. Commit and push `state.json`.

### Behavior:
* Tickets with ID `<= 37350` will **not** trigger notifications or historical watcher Issues.
* Only tickets with ID `> 37350` discovered after initial deployment will trigger new watcher Issues and notifications.
* After processing new tickets, `last_seen_id` automatically advances to the latest successfully processed ticket ID.

---

## State File (`state.json`)

`state.json` contains two conceptual sections:

```json
{
  "sources": {
    "django": {
      "last_seen_id": 37351
    }
  },
  "tracked": {
    "django:37351": {
      "source": "django",
      "ticket_id": 37351,
      "watcher_issue_number": 15,
      "status": "assigned",
      "notification_comment_created": true,
      "last_checked": "2026-09-05T18:00:00Z",
      "last_updated": "2026-09-05T17:30:00Z",
      "ticket_data": {
        "id": 37351,
        "title": "Cannot assign expressions to spatial fields",
        "owner": "Md. Saikat Islam",
        "component": "GIS",
        "pr_url": "https://github.com/django/django/pull/21893",
        "pr_status": "open"
      }
    }
  }
}
```

* **`sources`**: Maintains permanent cursor (`last_seen_id`) per source. `last_seen_id` is **never** reset or deleted when a ticket finishes.
* **`tracked`**: Contains active tickets currently being monitored using `source:ticket_id` (e.g. `"django:37351"`) as unique identity key.

---

## Configuration (`config.yaml`)

Configuration defines target repository, user notification handle, and active sources:

```yaml
watcher_repository: "saikat709/ticket-watcher"

notification_user: "saikat709"

sources:
  - id: "django"
    type: "django_trac"
    url: "https://code.djangoproject.com"

  # Example future GitHub repository sources:
  # - id: "pylint"
  #   type: "github"
  #   repository: "pylint-dev/pylint"
```

---

## GitHub Actions Workflows

Two workflows in `.github/workflows/` manage automated tasks:

1. **`discover.yml`**: Scheduled every 30 minutes (`cron: "*/30 * * * *"` and manual `workflow_dispatch`).
   - Fetches new tickets > `last_seen_id`.
   - Creates watcher GitHub Issue and initial notification comment (`@saikat709 — New ticket detected. Please check this out.`).
   - Updates `last_seen_id` and commits `state.json`.

2. **`update.yml`**: Scheduled every 24 hours (`cron: "0 0 * * *"` and manual `workflow_dispatch`).
   - Checks active tickets in `tracked`.
   - Detects status changes, owner changes, patch updates, pull requests, and PR merge state.
   - Updates watcher Issue body and posts update summary.
   - When PR is merged or ticket resolved: updates watcher Issue with `✅ Completed`, posts final completion comment, and removes ticket from `tracked` (while preserving `last_seen_id`).

### Permissions & Secrets Required

In repository **Settings → Actions → General → Workflow permissions**:
* Select **Read and write permissions**.
* The workflows use `secrets.GITHUB_TOKEN` automatically provided by GitHub Actions.

---

## Features & Design Principles

1. **Every New Ticket Triggers Notification**:
   - Ticket Watcher does **not** filter tickets based on whether they are "easy" or suitable for beginners.
   - Metadata flags like `easy-pickings`, `has-patch`, `needs-tests`, `UI/UX` are displayed in Issue body as labels, not used for filtering.

2. **Duplicate Prevention**:
   - Uses `source:ticket_id` as unique key.
   - Checks `tracked` state AND searches GitHub Issues in the watcher repository before issue creation.
   - Idempotent against workflow crashes, retries, and network timeouts.

3. **Explicit Notifications**:
   - Does NOT assign watcher Issue to user.
   - Posts a dedicated comment mentioning `@saikat709` after Issue creation to reliably trigger a GitHub notification.
   - Does NOT mention `@saikat709` on standard 24-hour updates to avoid notification noise.

4. **Source Abstraction**:
   - Generic `TicketSource` interface (`watcher/sources/base.py`).
   - Extensible architecture supports adding GitHub repositories (`GitHubSource`) or custom trackers cleanly.

---

## Local Execution & Testing

### Running Locally

Install dependencies:
```bash
pip install -r requirements.txt
```

Run Discovery job in dry-run mode (without posting to GitHub API):
```bash
python -m watcher.main discover --dry-run
```

Run 24-Hour Tracking job in dry-run mode:
```bash
python -m watcher.main update --dry-run
```

### Running Unit Tests

Run the complete test suite with mocks:
```bash
python -m unittest discover tests
```

---

## Completed Tickets vs Permanent History

When a ticket's pull request is merged or status is resolved:
1. The watcher GitHub Issue is updated with a `✅ Completed` summary.
2. A completion comment is posted explaining the resolution.
3. The ticket is removed from `tracked` in `state.json`.
4. The watcher GitHub Issue remains permanently in your repository as history.
5. The `last_seen_id` in `state.json` remains saved so the completed ticket is never rediscovered.
