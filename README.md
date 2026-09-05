# Open-Source Ticket Watcher

Stateful Python watcher powered by **GitHub Actions** to monitor open-source issue trackers (e.g., **Django Trac**, GitHub repos).

Discovers new tickets, creates GitHub Issues in your personal watcher repo, and mentions `@saikat709` via a separate comment. Continuously tracks active tickets every 24 hours for status updates, PR links, and merges until completion.

---

## ⚠️ Important: Manual Initial Setup

> [!IMPORTANT]
> The initial `last_seen_id` is **NOT** auto-discovered. You must manually inspect the source tracker and set the baseline ticket ID in `state.json` before enabling discovery.

Set `state.json` baseline:
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
* Tickets `<= 37350` will be ignored.
* Only new tickets `> 37350` will trigger watcher Issues & `@saikat709` mentions.

---

## Workflows & Schedules

| Workflow | Triggers | Frequency | Action |
| --- | --- | --- | --- |
| **`discover.yml`** | `push` (main), `schedule`, `workflow_dispatch` | Every 30 mins | Detects new tickets > `last_seen_id`, creates watcher Issue, posts `@saikat709` comment, updates `last_seen_id` |
| **`update.yml`** | `schedule`, `workflow_dispatch` | Every 24 hours | Checks active `tracked` tickets, posts updates, removes completed/merged tickets |

**Permissions**: Set GitHub Actions Workflow permissions to **Read and write permissions**.

---

## Configuration & State

* **`config.yaml`**: Defines target repo (`saikat709/ticket-watcher`), notification handle (`saikat709`), and active sources.
* **`state.json`**:
  * `sources`: Permanent cursor (`last_seen_id`) per tracker source.
  * `tracked`: Active tickets under key `source:ticket_id` (e.g. `django:37351`).

---

## Local Usage & Testing

### 1. Local Dry-Run Execution
```bash
pip install -r requirements.txt

# Run discovery job locally
python3 -m watcher.main discover --dry-run

# Run 24-hour tracking update locally
python3 -m watcher.main update --dry-run
```

### 2. Unit Testing
```bash
# Run complete test suite
python3 -m unittest discover tests

# Verbose test run
python3 -m unittest discover tests -v

# Run individual test modules
python3 -m unittest tests/test_state.py
python3 -m unittest tests/test_discovery.py
python3 -m unittest tests/test_tracking.py
python3 -m unittest tests/test_completion.py
```

---

## Key Design Principles

1. **No Beginner Filtering**: Every genuinely new ticket triggers a notification regardless of difficulty or labels.
2. **Duplicate Safe**: Uses `source:ticket_id` and searches existing watcher Issues to prevent duplicates on retries.
3. **Explicit Mention**: Posts a separate `@saikat709` comment on Issue creation for direct notifications.
4. **Permanent History**: Completed/merged tickets are removed from `tracked` while watcher Issues remain permanently in your repository.
