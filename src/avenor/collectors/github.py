from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from avenor.services.repositories import parse_repository_url


@dataclass(slots=True)
class GitHubRepositorySnapshot:
    repository: dict[str, Any]
    languages: dict[str, int]
    contributors: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    pull_requests: list[dict[str, Any]]
    releases: list[dict[str, Any]]


class GitHubCollector:
    def __init__(self, token: str | None) -> None:
        self.token = token
        self.base_url = "https://api.github.com"
        self.default_cap = 250 if token else 25

    def collect(self, url: str) -> GitHubRepositorySnapshot:
        parsed = parse_repository_url(url)
        with httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            repo_payload = self._request_json(client, f"/repos/{parsed.full_name}")
            languages = self._request_json(client, f"/repos/{parsed.full_name}/languages")
            contributors = [
                self._map_contributor(item)
                for item in self._paginate(
                    client,
                    f"/repos/{parsed.full_name}/contributors?per_page=100",
                    limit=self.default_cap,
                )
            ]

            issues = [
                self._map_issue(item)
                for item in self._paginate(
                    client,
                    f"/repos/{parsed.full_name}/issues?state=all&per_page=100",
                    limit=self.default_cap,
                )
                if "pull_request" not in item
            ]

            pull_requests: list[dict[str, Any]] = []
            for item in self._paginate(
                client,
                f"/repos/{parsed.full_name}/pulls?state=all&per_page=100",
                limit=self.default_cap,
            ):
                detailed = self._request_json(client, item["url"])
                pull_requests.append(self._map_pull_request(detailed))

            releases = [
                self._map_release(item)
                for item in self._paginate(
                    client,
                    f"/repos/{parsed.full_name}/releases?per_page=100",
                    limit=self.default_cap,
                )
            ]

        return GitHubRepositorySnapshot(
            repository=self._map_repository(repo_payload),
            languages={str(key): int(value) for key, value in languages.items()},
            contributors=contributors,
            issues=issues,
            pull_requests=pull_requests,
            releases=releases,
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "avenor",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request_json(self, client: httpx.Client, path_or_url: str) -> Any:
        response = client.get(path_or_url)
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise RuntimeError("GitHub API rate limit exceeded. Set AVENOR_GITHUB_TOKEN and retry.")
        response.raise_for_status()
        return response.json()

    def _paginate(self, client: httpx.Client, initial_path: str, limit: int | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        next_url: str | None = initial_path

        while next_url:
            response = client.get(next_url)
            if response.status_code == 403 and "rate limit" in response.text.lower():
                raise RuntimeError("GitHub API rate limit exceeded. Set AVENOR_GITHUB_TOKEN and retry.")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise RuntimeError(f"Expected list payload from GitHub, got {type(payload)!r}")

            results.extend(payload)
            if limit is not None and len(results) >= limit:
                return results[:limit]
            next_url = response.links.get("next", {}).get("url")
        return results

    def _map_repository(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": payload["id"],
            "description": payload.get("description"),
            "homepage_url": payload.get("homepage"),
            "default_branch": payload.get("default_branch"),
            "primary_language": payload.get("language"),
            "stars": payload.get("stargazers_count", 0),
            "forks": payload.get("forks_count", 0),
            "open_issues": payload.get("open_issues_count", 0),
            "archived": payload.get("archived", False),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
        }

    def _map_contributor(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": "github",
            "external_id": payload.get("id"),
            "login": payload.get("login"),
            "display_name": payload.get("login"),
            "email": None,
            "avatar_url": payload.get("avatar_url"),
            "first_seen_at": None,
            "last_seen_at": None,
            "contributions_count": payload.get("contributions", 0),
        }

    def _map_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": payload["id"],
            "number": payload["number"],
            "title": payload["title"],
            "state": payload["state"],
            "author_login": (payload.get("user") or {}).get("login"),
            "comments_count": payload.get("comments", 0),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "closed_at": payload.get("closed_at"),
        }

    def _map_pull_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": payload["id"],
            "number": payload["number"],
            "title": payload["title"],
            "state": payload["state"],
            "author_login": (payload.get("user") or {}).get("login"),
            "comments_count": payload.get("comments", 0),
            "review_comments_count": payload.get("review_comments", 0),
            "commits_count": payload.get("commits", 0),
            "additions": payload.get("additions", 0),
            "deletions": payload.get("deletions", 0),
            "changed_files": payload.get("changed_files", 0),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "closed_at": payload.get("closed_at"),
            "merged_at": payload.get("merged_at"),
        }

    def _map_release(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": payload["id"],
            "tag_name": payload["tag_name"],
            "name": payload.get("name"),
            "body": payload.get("body"),
            "draft": payload.get("draft", False),
            "prerelease": payload.get("prerelease", False),
            "published_at": payload.get("published_at"),
        }
