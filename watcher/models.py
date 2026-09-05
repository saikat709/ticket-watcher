from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Ticket:
    id: int
    source_id: str
    title: str
    description: str
    status: str
    resolution: str = ""
    created_at: str = ""
    updated_at: str = ""
    reporter: str = ""
    owner: str = ""
    component: str = ""
    priority: str = ""
    severity: str = ""
    triage_stage: str = ""
    labels: List[str] = field(default_factory=list)
    url: str = ""
    pr_url: Optional[str] = None
    pr_status: Optional[str] = None  # "open", "closed", "merged"
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source_id}:{self.id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "resolution": self.resolution,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reporter": self.reporter,
            "owner": self.owner,
            "component": self.component,
            "priority": self.priority,
            "severity": self.severity,
            "triage_stage": self.triage_stage,
            "labels": self.labels,
            "url": self.url,
            "pr_url": self.pr_url,
            "pr_status": self.pr_status,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ticket":
        return cls(
            id=int(data["id"]),
            source_id=data["source_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", ""),
            resolution=data.get("resolution", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            reporter=data.get("reporter", ""),
            owner=data.get("owner", ""),
            component=data.get("component", ""),
            priority=data.get("priority", ""),
            severity=data.get("severity", ""),
            triage_stage=data.get("triage_stage", ""),
            labels=data.get("labels", []),
            url=data.get("url", ""),
            pr_url=data.get("pr_url"),
            pr_status=data.get("pr_status"),
            raw_data=data.get("raw_data", {}),
        )


@dataclass
class SourceConfig:
    id: str
    type: str
    url: Optional[str] = None
    repository: Optional[str] = None


@dataclass
class WatcherConfig:
    watcher_repository: str
    notification_user: str
    sources: List[SourceConfig]
