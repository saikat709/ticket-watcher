import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        self.headers = {
            "User-Agent": "TicketWatcher/1.0 (+https://github.com/saikat709/ticket-watcher)",
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body_bytes = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body_bytes, headers=self.headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                res_text = resp.read().decode("utf-8")
                return json.loads(res_text) if res_text else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API error HTTP {e.code} on {method} {url}: {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"GitHub request failed on {method} {url}: {str(e)}") from e

    def create_issue(self, repo: str, title: str, body: str, labels: Optional[List[str]] = None) -> Dict[str, Any]:
        url = f"https://api.github.com/repos/{repo}/issues"
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return self._request("POST", url, payload)

    def update_issue(
        self,
        repo: str,
        issue_number: int,
        body: Optional[str] = None,
        title: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
        payload: Dict[str, Any] = {}
        if body is not None:
            payload["body"] = body
        if title is not None:
            payload["title"] = title
        if state is not None:
            payload["state"] = state
        return self._request("PATCH", url, payload)

    def create_comment(self, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
        payload = {"body": body}
        return self._request("POST", url, payload)

    def search_issue(self, repo: str, query_title: str) -> Optional[int]:
        """Search issues in repo by exact title match or search query to find issue number if it exists."""
        encoded_query = urllib.parse.quote(f"repo:{repo} in:title \"{query_title}\"")
        url = f"https://api.github.com/search/issues?q={encoded_query}"
        try:
            data = self._request("GET", url)
            items = data.get("items", [])
            for item in items:
                if item.get("title") == query_title:
                    return int(item["number"])
            if items:
                return int(items[0]["number"])
        except Exception:
            pass
        return None
