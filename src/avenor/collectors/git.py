from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import run
from typing import Any

from avenor.services.repositories import parse_repository_url


@dataclass(slots=True)
class GitRepositorySnapshot:
    contributors: list[dict[str, Any]]
    commits: list[dict[str, Any]]


class GitCollector:
    def __init__(self, repos_dir: Path) -> None:
        self.repos_dir = repos_dir

    def collect(self, url: str, default_branch: str | None = None) -> GitRepositorySnapshot:
        repo_path = self._ensure_local_clone(url, default_branch)
        commits = self._collect_commits(repo_path)
        contributors = self._aggregate_contributors(commits)
        return GitRepositorySnapshot(contributors=contributors, commits=commits)

    def _ensure_local_clone(self, url: str, default_branch: str | None) -> Path:
        parsed = parse_repository_url(url)
        target = self.repos_dir / f"{parsed.owner}__{parsed.name}"
        if target.exists():
            self._run_git(["-C", str(target), "fetch", "--all", "--prune"])
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            self._run_git(["clone", url, str(target)])

        branch = default_branch or "HEAD"
        if branch != "HEAD":
            self._run_git(["-C", str(target), "checkout", branch])
            self._run_git(["-C", str(target), "reset", "--hard", f"origin/{branch}"])
        return target

    def _collect_commits(self, repo_path: Path) -> list[dict[str, Any]]:
        output = self._run_git(
            [
                "-C",
                str(repo_path),
                "log",
                "--date=iso-strict",
                "--pretty=format:%x1e%H%x1f%an%x1f%ae%x1f%aI%x1f%s",
                "--numstat",
                "--no-renames",
            ]
        )
        commits: list[dict[str, Any]] = []
        for record in output.split("\x1e"):
            record = record.strip()
            if not record:
                continue

            lines = [line for line in record.splitlines() if line.strip()]
            header = lines[0].split("\x1f")
            sha, author_name, author_email, authored_at, message = header[:5]
            files: list[dict[str, Any]] = []
            additions = 0
            deletions = 0
            for line in lines[1:]:
                parts = line.split("\t", 2)
                if len(parts) != 3:
                    continue
                add_raw, del_raw, path = parts
                file_additions = self._numstat_value(add_raw)
                file_deletions = self._numstat_value(del_raw)
                additions += file_additions
                deletions += file_deletions
                files.append(
                    {
                        "path": path,
                        "additions": file_additions,
                        "deletions": file_deletions,
                    }
                )

            commits.append(
                {
                    "sha": sha,
                    "message": message,
                    "author_name": author_name or None,
                    "author_email": author_email or None,
                    "authored_at": authored_at,
                    "additions": additions,
                    "deletions": deletions,
                    "files_changed": len(files),
                    "files": files,
                }
            )
        return commits

    def _aggregate_contributors(self, commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "source": "git",
                "external_id": None,
                "login": None,
                "display_name": None,
                "email": None,
                "avatar_url": None,
                "first_seen_at": None,
                "last_seen_at": None,
                "contributions_count": 0,
            }
        )

        for commit in commits:
            email = commit.get("author_email") or "<unknown>"
            authored_at = commit.get("authored_at")
            contributor = aggregate[email]
            contributor["display_name"] = commit.get("author_name")
            contributor["email"] = None if email == "<unknown>" else email
            contributor["contributions_count"] += 1

            if authored_at is not None:
                current_seen = datetime.fromisoformat(str(authored_at).replace("Z", "+00:00"))
                first_seen = contributor["first_seen_at"]
                last_seen = contributor["last_seen_at"]
                if first_seen is None or current_seen < first_seen:
                    contributor["first_seen_at"] = current_seen
                if last_seen is None or current_seen > last_seen:
                    contributor["last_seen_at"] = current_seen

        return list(aggregate.values())

    def _numstat_value(self, raw: str) -> int:
        if raw == "-" or raw == "":
            return 0
        return int(raw)

    def _run_git(self, args: list[str]) -> str:
        command = ["git", *args]
        result = run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"git command failed: {' '.join(command)}")
        return result.stdout
