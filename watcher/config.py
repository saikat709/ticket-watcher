import os
import yaml
from pathlib import Path
from typing import Union
from .models import WatcherConfig, SourceConfig


def load_config(config_path: Union[str, Path] = "config.yaml") -> WatcherConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {path.resolve()}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    watcher_repo = os.getenv("GITHUB_REPOSITORY", data.get("watcher_repository", ""))
    notification_user = os.getenv("NOTIFICATION_USER", data.get("notification_user", ""))

    sources_data = data.get("sources", [])
    sources = []
    for s in sources_data:
        sources.append(
            SourceConfig(
                id=s["id"],
                type=s["type"],
                url=s.get("url"),
                repository=s.get("repository"),
            )
        )

    return WatcherConfig(
        watcher_repository=watcher_repo,
        notification_user=notification_user,
        sources=sources,
    )
