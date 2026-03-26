from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from avenor.models import Commit, Contributor, Issue, PullRequest, Release, Repository


def _bucket_label(value: datetime | None, period: str = "month") -> str:
    if value is None:
        return "Unknown"
    if period == "day":
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m")


def _sort_bucket_items(items: dict[str, int]) -> list[dict[str, Any]]:
    return [{"label": label, "value": items[label]} for label in sorted(items.keys())]


def get_overview(session: Session, repository_id: int) -> dict[str, Any]:
    session.flush()
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise ValueError(f"Repository {repository_id} does not exist.")

    issues_count = session.query(Issue).filter(Issue.repository_id == repository_id).count()
    pull_requests_count = session.query(PullRequest).filter(PullRequest.repository_id == repository_id).count()
    commits_count = session.query(Commit).filter(Commit.repository_id == repository_id).count()
    contributors_count = session.query(Contributor).filter(Contributor.repository_id == repository_id).count()
    releases_count = session.query(Release).filter(Release.repository_id == repository_id).count()

    return {
        "repository": repository,
        "issues_count": issues_count,
        "pull_requests_count": pull_requests_count,
        "commits_count": commits_count,
        "contributors_count": contributors_count,
        "releases_count": releases_count,
        "languages": repository.languages or {},
        "recent_releases": get_recent_releases(session, repository_id, limit=8),
    }


def get_activity_series(session: Session, repository_id: int, period: str = "month") -> dict[str, list[dict[str, Any]]]:
    session.flush()
    commits = session.scalars(select(Commit).where(Commit.repository_id == repository_id)).all()
    issues = session.scalars(select(Issue).where(Issue.repository_id == repository_id)).all()
    pull_requests = session.scalars(select(PullRequest).where(PullRequest.repository_id == repository_id)).all()

    commit_buckets: dict[str, int] = defaultdict(int)
    issue_buckets: dict[str, int] = defaultdict(int)
    pr_buckets: dict[str, int] = defaultdict(int)

    for commit in commits:
        commit_buckets[_bucket_label(commit.authored_at, period)] += 1
    for issue in issues:
        issue_buckets[_bucket_label(issue.created_at, period)] += 1
    for pull_request in pull_requests:
        pr_buckets[_bucket_label(pull_request.created_at, period)] += 1

    return {
        "commits": _sort_bucket_items(commit_buckets),
        "issues": _sort_bucket_items(issue_buckets),
        "pull_requests": _sort_bucket_items(pr_buckets),
    }


def get_new_contributors_series(session: Session, repository_id: int, period: str = "month") -> list[dict[str, Any]]:
    session.flush()
    contributors = session.scalars(select(Contributor).where(Contributor.repository_id == repository_id)).all()
    buckets: dict[str, int] = defaultdict(int)
    for contributor in contributors:
        buckets[_bucket_label(contributor.first_seen_at, period)] += 1
    return _sort_bucket_items(buckets)


def get_top_contributors(session: Session, repository_id: int, limit: int = 10) -> list[dict[str, Any]]:
    session.flush()
    contributors = session.scalars(
        select(Contributor).where(Contributor.repository_id == repository_id)
    ).all()
    ranked = sorted(contributors, key=lambda item: item.contributions_count, reverse=True)
    return [
        {
            "label": contributor.display_name or contributor.login or contributor.email or "Unknown",
            "value": contributor.contributions_count,
        }
        for contributor in ranked[:limit]
    ]


def get_language_breakdown(session: Session, repository_id: int) -> list[dict[str, Any]]:
    session.flush()
    repository = session.get(Repository, repository_id)
    if repository is None or not repository.languages:
        return []
    ranked = sorted(repository.languages.items(), key=lambda item: item[1], reverse=True)
    return [{"label": label, "value": value} for label, value in ranked]


def get_commit_domain_breakdown(session: Session, repository_id: int, limit: int = 10) -> list[dict[str, Any]]:
    session.flush()
    commits = session.scalars(select(Commit).where(Commit.repository_id == repository_id)).all()
    counts: Counter[str] = Counter()
    for commit in commits:
        email = commit.author_email or ""
        domain = email.split("@", 1)[1].lower() if "@" in email else "unknown"
        counts[domain] += 1
    return [{"label": label, "value": value} for label, value in counts.most_common(limit)]


def get_recent_releases(session: Session, repository_id: int, limit: int = 8) -> list[Release]:
    session.flush()
    releases = session.scalars(select(Release).where(Release.repository_id == repository_id)).all()
    floor = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(releases, key=lambda release: release.published_at or floor, reverse=True)
    return ordered[:limit]
