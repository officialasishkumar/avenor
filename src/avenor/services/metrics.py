"""Analytics and metrics service — CHAOSS-inspired open-source health metrics.

Mirrors the rich analytics from Augur's metrics layer and 8knot's visualizations.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from avenor.models import Commit, CommitFile, Contributor, Issue, PullRequest, Release, Repository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bucket_label(value: datetime | None, period: str = "month") -> str:
    if value is None:
        return "Unknown"
    if period == "day":
        return value.strftime("%Y-%m-%d")
    if period == "week":
        return value.strftime("%Y-W%W")
    return value.strftime("%Y-%m")


def _sort_bucket_items(items: dict[str, int]) -> list[dict[str, Any]]:
    return [{"label": label, "value": items[label]} for label in sorted(items.keys()) if label != "Unknown"]


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[f]
    return s[f] + (k - f) * (s[c] - s[f])


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def get_overview(session: Session, repository_id: int) -> dict[str, Any]:
    session.flush()
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise ValueError(f"Repository {repository_id} does not exist.")

    issues_count = session.query(Issue).filter(Issue.repository_id == repository_id).count()
    prs_count = session.query(PullRequest).filter(PullRequest.repository_id == repository_id).count()
    commits_count = session.query(Commit).filter(Commit.repository_id == repository_id).count()
    contributors_count = session.query(Contributor).filter(Contributor.repository_id == repository_id).count()
    releases_count = session.query(Release).filter(Release.repository_id == repository_id).count()

    open_issues = session.query(Issue).filter(
        Issue.repository_id == repository_id, Issue.state == "open"
    ).count()
    open_prs = session.query(PullRequest).filter(
        PullRequest.repository_id == repository_id, PullRequest.state == "open"
    ).count()
    merged_prs = session.query(PullRequest).filter(
        PullRequest.repository_id == repository_id, PullRequest.merged_at.isnot(None)
    ).count()

    return {
        "repository": repository,
        "issues_count": issues_count,
        "pull_requests_count": prs_count,
        "commits_count": commits_count,
        "contributors_count": contributors_count,
        "releases_count": releases_count,
        "open_issues": open_issues,
        "open_prs": open_prs,
        "merged_prs": merged_prs,
        "merge_rate": round(merged_prs / prs_count * 100, 1) if prs_count else 0,
        "languages": repository.languages or {},
        "recent_releases": get_recent_releases(session, repository_id, limit=8),
    }


# ---------------------------------------------------------------------------
# Activity time series
# ---------------------------------------------------------------------------

def get_activity_series(session: Session, repository_id: int, period: str = "month") -> dict[str, list[dict[str, Any]]]:
    session.flush()
    commits = session.scalars(select(Commit).where(Commit.repository_id == repository_id)).all()
    issues = session.scalars(select(Issue).where(Issue.repository_id == repository_id)).all()
    prs = session.scalars(select(PullRequest).where(PullRequest.repository_id == repository_id)).all()

    commit_buckets: dict[str, int] = defaultdict(int)
    issue_buckets: dict[str, int] = defaultdict(int)
    pr_buckets: dict[str, int] = defaultdict(int)

    for c in commits:
        commit_buckets[_bucket_label(c.authored_at, period)] += 1
    for i in issues:
        issue_buckets[_bucket_label(i.created_at, period)] += 1
    for p in prs:
        pr_buckets[_bucket_label(p.created_at, period)] += 1

    return {
        "commits": _sort_bucket_items(commit_buckets),
        "issues": _sort_bucket_items(issue_buckets),
        "pull_requests": _sort_bucket_items(pr_buckets),
    }


# ---------------------------------------------------------------------------
# Contributor metrics (8knot-inspired)
# ---------------------------------------------------------------------------

def get_new_contributors_series(session: Session, repository_id: int, period: str = "month") -> list[dict[str, Any]]:
    session.flush()
    contributors = session.scalars(select(Contributor).where(Contributor.repository_id == repository_id)).all()
    buckets: dict[str, int] = defaultdict(int)
    for c in contributors:
        buckets[_bucket_label(c.first_seen_at, period)] += 1
    return _sort_bucket_items(buckets)


def get_top_contributors(session: Session, repository_id: int, limit: int = 15) -> list[dict[str, Any]]:
    session.flush()
    contributors = session.scalars(
        select(Contributor).where(Contributor.repository_id == repository_id)
    ).all()
    ranked = sorted(contributors, key=lambda c: c.contributions_count, reverse=True)
    return [
        {
            "label": c.display_name or c.login or c.email or "Unknown",
            "value": c.contributions_count,
            "login": c.login,
            "avatar_url": c.avatar_url,
        }
        for c in ranked[:limit]
    ]


def get_contributor_types(session: Session, repository_id: int) -> dict[str, Any]:
    """Classify contributors as drive-by (1 contribution), repeat, or core."""
    session.flush()
    contributors = session.scalars(
        select(Contributor).where(Contributor.repository_id == repository_id)
    ).all()

    drive_by = repeat = core = 0
    for c in contributors:
        count = c.contributions_count
        if count <= 1:
            drive_by += 1
        elif count <= 10:
            repeat += 1
        else:
            core += 1

    return {
        "drive_by": drive_by,
        "repeat": repeat,
        "core": core,
        "total": len(contributors),
    }


def get_bus_factor(session: Session, repository_id: int) -> dict[str, Any]:
    """Bus factor: smallest set of contributors accounting for 50%+ of commits."""
    session.flush()
    contributors = session.scalars(
        select(Contributor).where(Contributor.repository_id == repository_id)
    ).all()

    ranked = sorted(contributors, key=lambda c: c.contributions_count, reverse=True)
    total = sum(c.contributions_count for c in ranked)
    if total == 0:
        return {"bus_factor": 0, "total_contributors": 0}

    cumulative = 0
    bus_factor = 0
    for c in ranked:
        cumulative += c.contributions_count
        bus_factor += 1
        if cumulative >= total * 0.5:
            break

    return {"bus_factor": bus_factor, "total_contributors": len(ranked)}


def get_contributor_activity_heatmap(session: Session, repository_id: int) -> list[dict[str, Any]]:
    """Commits per day-of-week and hour — activity heatmap data."""
    session.flush()
    commits = session.scalars(select(Commit).where(Commit.repository_id == repository_id)).all()

    heatmap: dict[tuple[int, int], int] = defaultdict(int)
    for c in commits:
        if c.authored_at:
            heatmap[(c.authored_at.weekday(), c.authored_at.hour)] += 1

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return [
        {"day": days[day], "hour": hour, "value": heatmap.get((day, hour), 0)}
        for day in range(7)
        for hour in range(24)
    ]


# ---------------------------------------------------------------------------
# Issue metrics
# ---------------------------------------------------------------------------

def get_issue_stats(session: Session, repository_id: int) -> dict[str, Any]:
    session.flush()
    issues = session.scalars(select(Issue).where(Issue.repository_id == repository_id)).all()

    total = len(issues)
    open_count = sum(1 for i in issues if i.state == "open")
    closed_count = sum(1 for i in issues if i.state == "closed")

    close_times: list[float] = []
    for i in issues:
        if i.closed_at and i.created_at:
            delta = (i.closed_at - i.created_at).total_seconds() / 3600
            close_times.append(delta)

    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "close_rate": round(closed_count / total * 100, 1) if total else 0,
        "median_close_time_hours": round(_median(close_times), 1),
        "p90_close_time_hours": round(_percentile(close_times, 90), 1),
        "avg_close_time_hours": round(sum(close_times) / len(close_times), 1) if close_times else 0,
    }


def get_issue_activity_series(session: Session, repository_id: int, period: str = "month") -> dict[str, list[dict[str, Any]]]:
    session.flush()
    issues = session.scalars(select(Issue).where(Issue.repository_id == repository_id)).all()

    opened: dict[str, int] = defaultdict(int)
    closed: dict[str, int] = defaultdict(int)

    for i in issues:
        opened[_bucket_label(i.created_at, period)] += 1
        if i.closed_at:
            closed[_bucket_label(i.closed_at, period)] += 1

    return {
        "opened": _sort_bucket_items(opened),
        "closed": _sort_bucket_items(closed),
    }


def get_issue_staleness(session: Session, repository_id: int) -> list[dict[str, Any]]:
    """Open issues grouped by staleness: <7d, <30d, <90d, >90d."""
    session.flush()
    now = datetime.now(timezone.utc)
    issues = session.scalars(
        select(Issue).where(Issue.repository_id == repository_id, Issue.state == "open")
    ).all()

    buckets = {"< 7 days": 0, "7-30 days": 0, "30-90 days": 0, "> 90 days": 0}
    for i in issues:
        ref = i.updated_at or i.created_at
        if ref is None:
            buckets["> 90 days"] += 1
            continue
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        age = (now - ref).days
        if age < 7:
            buckets["< 7 days"] += 1
        elif age < 30:
            buckets["7-30 days"] += 1
        elif age < 90:
            buckets["30-90 days"] += 1
        else:
            buckets["> 90 days"] += 1

    return [{"label": k, "value": v} for k, v in buckets.items()]


def get_top_issue_authors(session: Session, repository_id: int, limit: int = 10) -> list[dict[str, Any]]:
    session.flush()
    issues = session.scalars(select(Issue).where(Issue.repository_id == repository_id)).all()
    counts: Counter[str] = Counter()
    for i in issues:
        counts[i.author_login or "unknown"] += 1
    return [{"label": k, "value": v} for k, v in counts.most_common(limit)]


# ---------------------------------------------------------------------------
# Pull request metrics
# ---------------------------------------------------------------------------

def get_pr_stats(session: Session, repository_id: int) -> dict[str, Any]:
    session.flush()
    prs = session.scalars(select(PullRequest).where(PullRequest.repository_id == repository_id)).all()

    total = len(prs)
    open_count = sum(1 for p in prs if p.state == "open")
    merged_count = sum(1 for p in prs if p.merged_at)
    closed_unmerged = sum(1 for p in prs if p.state == "closed" and not p.merged_at)

    merge_times: list[float] = []
    total_additions = 0
    total_deletions = 0
    for p in prs:
        if p.merged_at and p.created_at:
            delta = (p.merged_at - p.created_at).total_seconds() / 3600
            merge_times.append(delta)
        total_additions += p.additions
        total_deletions += p.deletions

    return {
        "total": total,
        "open": open_count,
        "merged": merged_count,
        "closed_unmerged": closed_unmerged,
        "merge_rate": round(merged_count / total * 100, 1) if total else 0,
        "median_merge_time_hours": round(_median(merge_times), 1),
        "p90_merge_time_hours": round(_percentile(merge_times, 90), 1),
        "avg_merge_time_hours": round(sum(merge_times) / len(merge_times), 1) if merge_times else 0,
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "avg_pr_size": round((total_additions + total_deletions) / total, 0) if total else 0,
    }


def get_pr_activity_series(session: Session, repository_id: int, period: str = "month") -> dict[str, list[dict[str, Any]]]:
    session.flush()
    prs = session.scalars(select(PullRequest).where(PullRequest.repository_id == repository_id)).all()

    opened: dict[str, int] = defaultdict(int)
    merged: dict[str, int] = defaultdict(int)
    closed: dict[str, int] = defaultdict(int)

    for p in prs:
        opened[_bucket_label(p.created_at, period)] += 1
        if p.merged_at:
            merged[_bucket_label(p.merged_at, period)] += 1
        elif p.closed_at:
            closed[_bucket_label(p.closed_at, period)] += 1

    return {
        "opened": _sort_bucket_items(opened),
        "merged": _sort_bucket_items(merged),
        "closed_unmerged": _sort_bucket_items(closed),
    }


def get_pr_size_distribution(session: Session, repository_id: int) -> list[dict[str, Any]]:
    """PR size buckets: XS (<10), S (<50), M (<200), L (<500), XL (500+)."""
    session.flush()
    prs = session.scalars(select(PullRequest).where(PullRequest.repository_id == repository_id)).all()

    buckets = {"XS (<10)": 0, "S (10-49)": 0, "M (50-199)": 0, "L (200-499)": 0, "XL (500+)": 0}
    for p in prs:
        size = p.additions + p.deletions
        if size < 10:
            buckets["XS (<10)"] += 1
        elif size < 50:
            buckets["S (10-49)"] += 1
        elif size < 200:
            buckets["M (50-199)"] += 1
        elif size < 500:
            buckets["L (200-499)"] += 1
        else:
            buckets["XL (500+)"] += 1

    return [{"label": k, "value": v} for k, v in buckets.items()]


def get_pr_merge_time_series(session: Session, repository_id: int, period: str = "month") -> list[dict[str, Any]]:
    """Average merge time per period."""
    session.flush()
    prs = session.scalars(select(PullRequest).where(PullRequest.repository_id == repository_id)).all()

    bucket_times: dict[str, list[float]] = defaultdict(list)
    for p in prs:
        if p.merged_at and p.created_at:
            hours = (p.merged_at - p.created_at).total_seconds() / 3600
            bucket_times[_bucket_label(p.merged_at, period)].append(hours)

    return [
        {"label": k, "value": round(sum(v) / len(v), 1)}
        for k, v in sorted(bucket_times.items())
    ]


def get_top_pr_authors(session: Session, repository_id: int, limit: int = 10) -> list[dict[str, Any]]:
    session.flush()
    prs = session.scalars(select(PullRequest).where(PullRequest.repository_id == repository_id)).all()
    counts: Counter[str] = Counter()
    for p in prs:
        counts[p.author_login or "unknown"] += 1
    return [{"label": k, "value": v} for k, v in counts.most_common(limit)]


# ---------------------------------------------------------------------------
# Codebase / file-level metrics
# ---------------------------------------------------------------------------

def get_hotspot_files(session: Session, repository_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """Most frequently changed files — contribution hotspot."""
    session.flush()
    commit_ids = select(Commit.id).where(Commit.repository_id == repository_id).subquery()
    files = session.scalars(
        select(CommitFile).where(CommitFile.commit_id.in_(select(commit_ids)))
    ).all()

    counts: Counter[str] = Counter()
    churn: dict[str, int] = defaultdict(int)
    for f in files:
        counts[f.path] += 1
        churn[f.path] += f.additions + f.deletions

    return [
        {"label": path, "value": count, "churn": churn[path]}
        for path, count in counts.most_common(limit)
    ]


def get_code_churn_series(session: Session, repository_id: int, period: str = "month") -> list[dict[str, Any]]:
    """Lines added + deleted per period — code churn."""
    session.flush()
    commits = session.scalars(select(Commit).where(Commit.repository_id == repository_id)).all()

    buckets: dict[str, int] = defaultdict(int)
    for c in commits:
        buckets[_bucket_label(c.authored_at, period)] += c.additions + c.deletions

    return _sort_bucket_items(buckets)


def get_file_type_breakdown(session: Session, repository_id: int) -> list[dict[str, Any]]:
    """Count of changed files grouped by extension."""
    session.flush()
    commit_ids = select(Commit.id).where(Commit.repository_id == repository_id).subquery()
    files = session.scalars(
        select(CommitFile).where(CommitFile.commit_id.in_(select(commit_ids)))
    ).all()

    counts: Counter[str] = Counter()
    for f in files:
        ext = f.path.rsplit(".", 1)[-1].lower() if "." in f.path else "other"
        counts[ext] += 1

    return [{"label": ext, "value": count} for ext, count in counts.most_common(15)]


# ---------------------------------------------------------------------------
# Domain / affiliation
# ---------------------------------------------------------------------------

def get_commit_domain_breakdown(session: Session, repository_id: int, limit: int = 10) -> list[dict[str, Any]]:
    session.flush()
    commits = session.scalars(select(Commit).where(Commit.repository_id == repository_id)).all()
    counts: Counter[str] = Counter()
    for c in commits:
        email = c.author_email or ""
        domain = email.split("@", 1)[1].lower() if "@" in email else "unknown"
        counts[domain] += 1
    return [{"label": k, "value": v} for k, v in counts.most_common(limit)]


def get_domain_activity_series(session: Session, repository_id: int, limit_domains: int = 5, period: str = "month") -> dict[str, list[dict[str, Any]]]:
    """Commits over time broken down by top email domains."""
    session.flush()
    commits = session.scalars(select(Commit).where(Commit.repository_id == repository_id)).all()

    domain_counts: Counter[str] = Counter()
    for c in commits:
        email = c.author_email or ""
        domain = email.split("@", 1)[1].lower() if "@" in email else "unknown"
        domain_counts[domain] += 1

    top_domains = [d for d, _ in domain_counts.most_common(limit_domains)]
    series: dict[str, dict[str, int]] = {d: defaultdict(int) for d in top_domains}

    for c in commits:
        email = c.author_email or ""
        domain = email.split("@", 1)[1].lower() if "@" in email else "unknown"
        if domain in series:
            series[domain][_bucket_label(c.authored_at, period)] += 1

    return {domain: _sort_bucket_items(buckets) for domain, buckets in series.items()}


# ---------------------------------------------------------------------------
# Language breakdown
# ---------------------------------------------------------------------------

def get_language_breakdown(session: Session, repository_id: int) -> list[dict[str, Any]]:
    session.flush()
    repository = session.get(Repository, repository_id)
    if repository is None or not repository.languages:
        return []
    ranked = sorted(repository.languages.items(), key=lambda item: item[1], reverse=True)
    return [{"label": label, "value": value} for label, value in ranked]


# ---------------------------------------------------------------------------
# Releases
# ---------------------------------------------------------------------------

def get_recent_releases(session: Session, repository_id: int, limit: int = 8) -> list[Release]:
    session.flush()
    releases = session.scalars(select(Release).where(Release.repository_id == repository_id)).all()
    floor = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(releases, key=lambda r: r.published_at or floor, reverse=True)
    return ordered[:limit]


def get_release_cadence(session: Session, repository_id: int) -> list[dict[str, Any]]:
    """Time between consecutive releases."""
    session.flush()
    releases = session.scalars(select(Release).where(Release.repository_id == repository_id)).all()
    floor = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(releases, key=lambda r: r.published_at or floor)

    gaps = []
    for i in range(1, len(ordered)):
        prev = ordered[i - 1].published_at
        curr = ordered[i].published_at
        if prev and curr:
            gaps.append({
                "label": ordered[i].tag_name,
                "value": round((curr - prev).total_seconds() / 86400, 1),
            })
    return gaps


# ---------------------------------------------------------------------------
# Multi-repo comparison
# ---------------------------------------------------------------------------

def get_comparison_stats(session: Session, repository_ids: list[int]) -> list[dict[str, Any]]:
    """Quick stats for multiple repositories for comparison view."""
    results = []
    for rid in repository_ids:
        repo = session.get(Repository, rid)
        if repo is None:
            continue
        commits = session.query(Commit).filter(Commit.repository_id == rid).count()
        prs = session.query(PullRequest).filter(PullRequest.repository_id == rid).count()
        issues = session.query(Issue).filter(Issue.repository_id == rid).count()
        contributors = session.query(Contributor).filter(Contributor.repository_id == rid).count()
        results.append({
            "id": rid,
            "full_name": repo.full_name,
            "commits": commits,
            "pull_requests": prs,
            "issues": issues,
            "contributors": contributors,
            "stars": repo.stars,
            "forks": repo.forks,
        })
    return results
