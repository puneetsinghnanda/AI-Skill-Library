"""GitHub interface for tsl pr and tsl ci-verify (SDD-04 §6.12, §6.13).

There is deliberately no merge method: no tool may merge (C-14,
merge_and_deploy: never). Authentication uses the engineer's existing git
credential; tsl stores no GitHub token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class GitHubUnavailable(Exception):
    pass


@dataclass
class PullRequest:
    number: int
    url: str
    draft: bool
    head_sha: str
    body: str
    changed_files: list[str]
    base_ref: str = "main"
    head_ref: str = ""


class GitHubClient(Protocol):
    def create_pull_request(
        self, repo: str, head: str, base: str, title: str, body: str, draft: bool, labels: list[str]
    ) -> PullRequest: ...
    def get_pull_request(self, repo: str, number: int) -> PullRequest: ...


def repo_slug(url: str) -> str:
    """git@github.com:org/name.git or https://github.com/org/name -> org/name"""
    s = url
    if s.startswith("git@"):
        s = s.split(":", 1)[1]
    elif "://" in s:
        s = s.split("://", 1)[1].split("/", 1)[1]
    return s.removesuffix(".git").strip("/")


class HttpGitHubClient:
    """REST through httpx, with the token taken from `git credential fill` per call."""

    def __init__(self, api_url: str, credential: str | None = None) -> None:
        self.api = api_url.rstrip("/")
        self._credential = credential

    def _token(self) -> str:
        if self._credential:
            return self._credential
        import subprocess
        from urllib.parse import urlparse

        host = urlparse(self.api).hostname or "github.com"
        host = "github.com" if host == "api.github.com" else host
        out = subprocess.run(
            ["git", "credential", "fill"],
            input=f"protocol=https\nhost={host}\n\n",
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        for line in out.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1]
        raise GitHubUnavailable("no git credential for host")

    def _req(self, method: str, path: str, body: object = None) -> object:
        import httpx

        try:
            r = httpx.request(
                method,
                self.api + path,
                json=body,
                timeout=15,
                headers={
                    "Authorization": f"Bearer {self._token()}",
                    "Accept": "application/vnd.github+json",
                },
            )
        except httpx.HTTPError as exc:
            raise GitHubUnavailable(type(exc).__name__) from exc
        if r.status_code >= 400:
            raise GitHubUnavailable(f"HTTP {r.status_code}")
        return r.json()

    def create_pull_request(
        self, repo: str, head: str, base: str, title: str, body: str, draft: bool, labels: list[str]
    ) -> PullRequest:
        d = self._req(
            "POST",
            f"/repos/{repo}/pulls",
            {"head": head, "base": base, "title": title, "body": body, "draft": draft},
        )
        if not isinstance(d, dict):
            raise GitHubUnavailable("unexpected response")
        if labels:
            self._req("POST", f"/repos/{repo}/issues/{d['number']}/labels", {"labels": labels})
        return PullRequest(
            int(d["number"]),
            str(d["html_url"]),
            bool(d.get("draft")),
            str(d["head"]["sha"]),
            body,
            [],
            base,
            head,
        )

    def get_pull_request(self, repo: str, number: int) -> PullRequest:
        d = self._req("GET", f"/repos/{repo}/pulls/{number}")
        files = self._req("GET", f"/repos/{repo}/pulls/{number}/files?per_page=300")
        if not isinstance(d, dict) or not isinstance(files, list):
            raise GitHubUnavailable("unexpected response")
        return PullRequest(
            number,
            str(d["html_url"]),
            bool(d.get("draft")),
            str(d["head"]["sha"]),
            str(d.get("body") or ""),
            [str(f["filename"]) for f in files],
            str(d["base"]["ref"]),
            str(d["head"]["ref"]),
        )
