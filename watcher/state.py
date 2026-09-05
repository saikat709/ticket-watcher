import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class StateManager:
    def __init__(self, state_path: str = "state.json"):
        self.state_path = Path(state_path)
        self.data: Dict[str, Any] = {"sources": {}, "tracked": {}}
        self.load()

    def load(self) -> None:
        if not self.state_path.exists():
            # If state file does not exist, initialize blank layout
            self.data = {"sources": {}, "tracked": {}}
            return

        with open(self.state_path, "r", encoding="utf-8") as f:
            try:
                content = json.load(f)
                if isinstance(content, dict):
                    self.data = content
                    if "sources" not in self.data:
                        self.data["sources"] = {}
                    if "tracked" not in self.data:
                        self.data["tracked"] = {}
                else:
                    self.data = {"sources": {}, "tracked": {}}
            except json.JSONDecodeError:
                self.data = {"sources": {}, "tracked": {}}

    def save(self) -> None:
        temp_path = self.state_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        temp_path.replace(self.state_path)

    def get_last_seen_id(self, source_id: str) -> Optional[int]:
        source = self.data.get("sources", {}).get(source_id)
        if source and "last_seen_id" in source:
            return int(source["last_seen_id"])
        return None

    def set_last_seen_id(self, source_id: str, last_seen_id: int) -> None:
        if "sources" not in self.data:
            self.data["sources"] = {}
        if source_id not in self.data["sources"]:
            self.data["sources"][source_id] = {}
        self.data["sources"][source_id]["last_seen_id"] = int(last_seen_id)

    def get_tracked_entry(self, key: str) -> Optional[Dict[str, Any]]:
        return self.data.get("tracked", {}).get(key)

    def is_tracked(self, key: str) -> bool:
        return key in self.data.get("tracked", {})

    def add_or_update_tracked(
        self,
        key: str,
        source_id: str,
        ticket_id: int,
        watcher_issue_number: int,
        ticket_data: Dict[str, Any],
        status: str,
        notification_comment_created: bool = True,
        last_updated: Optional[str] = None,
        last_checked: Optional[str] = None,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if "tracked" not in self.data:
            self.data["tracked"] = {}

        existing = self.data["tracked"].get(key, {})
        entry = {
            "source": source_id,
            "ticket_id": ticket_id,
            "watcher_issue_number": watcher_issue_number,
            "status": status,
            "notification_comment_created": notification_comment_created,
            "last_checked": last_checked or now_iso,
            "last_updated": last_updated or existing.get("last_updated") or now_iso,
            "ticket_data": ticket_data,
        }
        self.data["tracked"][key] = entry

    def remove_tracked(self, key: str) -> bool:
        """Removes a ticket from tracked state upon completion.
        IMPORTANT: Does NOT remove or modify source cursor (last_seen_id).
        """
        if "tracked" in self.data and key in self.data["tracked"]:
            del self.data["tracked"][key]
            return True
        return False

    def get_all_tracked(self) -> Dict[str, Dict[str, Any]]:
        return self.data.get("tracked", {})
