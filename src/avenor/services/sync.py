from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from avenor.config import get_github_token, get_settings
from avenor.models import (
    CollectionJob,
    Commit,
    CommitFile,
    Contributor,
    Issue,
    JobRun,
    PullRequest,
    Release,
    Repository,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _ensure_job(session: Session, repository: Repository, collector: str) -> CollectionJob:
    stmt = select(CollectionJob).where(
        CollectionJob.repository_id == repository.id,
        CollectionJob.collector == collector,
    )
    job = session.scalars(stmt).first()
    if job:
        return job

    job = CollectionJob(repository_id=repository.id, collector=collector)
    session.add(job)
    session.flush()
    return job


def _start_job_run(session: Session, job: CollectionJob) -> JobRun:
    job.status = "running"
    job.started_at = _utcnow()
    job.last_error = None
    run = JobRun(job_id=job.id, status="running")
    session.add(run)
    session.flush()
    return run


def _finish_job_run(job: CollectionJob, run: JobRun, status: str, records_written: int = 0, error: str | None = None) -> None:
    finished_at = _utcnow()
    job.status = status
    job.finished_at = finished_at
    job.last_error = error
    run.status = status
    run.finished_at = finished_at
    run.records_written = records_written
    run.error = error


def _replace_repository_children(session: Session, repository: Repository) -> None:
    commit_ids = select(Commit.id).where(Commit.repository_id == repository.id)
    session.execute(delete(CommitFile).where(CommitFile.commit_id.in_(commit_ids)))
    session.execute(delete(Issue).where(Issue.repository_id == repository.id))
    session.execute(delete(PullRequest).where(PullRequest.repository_id == repository.id))
    session.execute(delete(Release).where(Release.repository_id == repository.id))
    session.execute(delete(Contributor).where(Contributor.repository_id == repository.id))
    session.execute(delete(Commit).where(Commit.repository_id == repository.id))


def sync_repository(session: Session, repository: Repository) -> Repository:
    settings = get_settings()
    from avenor.collectors.git import GitCollector
    from avenor.collectors.github import GitHubCollector

    repository.sync_status = "running"
    repository.sync_error = None
    session.flush()

    git_job = _ensure_job(session, repository, "git")

    if repository.host == "github.com":
        github_job = _ensure_job(session, repository, "github")
        github_run = _start_job_run(session, github_job)
        try:
            github_snapshot = GitHubCollector(get_github_token()).collect(repository.url)
            _replace_repository_children(session, repository)
            _apply_github_snapshot(session, repository, github_snapshot)
            _finish_job_run(
                github_job,
                github_run,
                status="ready",
                records_written=(
                    len(github_snapshot.issues)
                    + len(github_snapshot.pull_requests)
                    + len(github_snapshot.releases)
                    + len(github_snapshot.contributors)
                ),
            )
        except Exception as exc:
            _finish_job_run(github_job, github_run, status="failed", error=str(exc))
            repository.sync_status = "failed"
            repository.sync_error = str(exc)
            raise
    else:
        _replace_repository_children(session, repository)

    git_run = _start_job_run(session, git_job)
    try:
        git_snapshot = GitCollector(settings.repos_dir).collect(
            repository.url,
            default_branch=repository.default_branch,
        )
        _apply_git_snapshot(session, repository, git_snapshot)
        _finish_job_run(git_job, git_run, status="ready", records_written=len(git_snapshot.commits))
    except Exception as exc:
        _finish_job_run(git_job, git_run, status="failed", error=str(exc))
        repository.sync_status = "failed"
        repository.sync_error = str(exc)
        raise

    repository.sync_status = "ready"
    repository.sync_error = None
    repository.last_synced_at = _utcnow()
    session.flush()
    return repository


def _apply_github_snapshot(session: Session, repository: Repository, snapshot: Any) -> None:
    payload = snapshot.repository
    repository.external_id = payload.get("external_id")
    repository.description = payload.get("description")
    repository.homepage_url = payload.get("homepage_url")
    repository.default_branch = payload.get("default_branch")
    repository.primary_language = payload.get("primary_language")
    repository.languages = snapshot.languages
    repository.stars = int(payload.get("stars") or 0)
    repository.forks = int(payload.get("forks") or 0)
    repository.open_issues = int(payload.get("open_issues") or 0)
    repository.archived = bool(payload.get("archived") or False)
    repository.created_at = _coerce_datetime(payload.get("created_at"))
    repository.updated_at = _coerce_datetime(payload.get("updated_at"))

    for contributor in snapshot.contributors:
        session.add(
            Contributor(
                repository_id=repository.id,
                source=contributor.get("source", "github"),
                external_id=str(contributor["external_id"]) if contributor.get("external_id") is not None else None,
                login=contributor.get("login"),
                display_name=contributor.get("display_name"),
                email=contributor.get("email"),
                avatar_url=contributor.get("avatar_url"),
                first_seen_at=_coerce_datetime(contributor.get("first_seen_at")),
                last_seen_at=_coerce_datetime(contributor.get("last_seen_at")),
                contributions_count=int(contributor.get("contributions_count") or 0),
            )
        )

    for issue in snapshot.issues:
        session.add(
            Issue(
                repository_id=repository.id,
                external_id=str(issue["external_id"]),
                number=int(issue["number"]),
                title=issue["title"],
                state=issue["state"],
                author_login=issue.get("author_login"),
                comments_count=int(issue.get("comments_count") or 0),
                created_at=_coerce_datetime(issue.get("created_at")),
                updated_at=_coerce_datetime(issue.get("updated_at")),
                closed_at=_coerce_datetime(issue.get("closed_at")),
            )
        )

    for pull_request in snapshot.pull_requests:
        session.add(
            PullRequest(
                repository_id=repository.id,
                external_id=str(pull_request["external_id"]),
                number=int(pull_request["number"]),
                title=pull_request["title"],
                state=pull_request["state"],
                author_login=pull_request.get("author_login"),
                comments_count=int(pull_request.get("comments_count") or 0),
                review_comments_count=int(pull_request.get("review_comments_count") or 0),
                commits_count=int(pull_request.get("commits_count") or 0),
                additions=int(pull_request.get("additions") or 0),
                deletions=int(pull_request.get("deletions") or 0),
                changed_files=int(pull_request.get("changed_files") or 0),
                created_at=_coerce_datetime(pull_request.get("created_at")),
                updated_at=_coerce_datetime(pull_request.get("updated_at")),
                closed_at=_coerce_datetime(pull_request.get("closed_at")),
                merged_at=_coerce_datetime(pull_request.get("merged_at")),
            )
        )

    for release in snapshot.releases:
        session.add(
            Release(
                repository_id=repository.id,
                external_id=str(release["external_id"]),
                tag_name=release["tag_name"],
                name=release.get("name"),
                body=release.get("body"),
                draft=bool(release.get("draft") or False),
                prerelease=bool(release.get("prerelease") or False),
                published_at=_coerce_datetime(release.get("published_at")),
            )
        )


def _apply_git_snapshot(session: Session, repository: Repository, snapshot: Any) -> None:
    for contributor in snapshot.contributors:
        session.add(
            Contributor(
                repository_id=repository.id,
                source=contributor.get("source", "git"),
                external_id=contributor.get("external_id"),
                login=contributor.get("login"),
                display_name=contributor.get("display_name"),
                email=contributor.get("email"),
                avatar_url=contributor.get("avatar_url"),
                first_seen_at=_coerce_datetime(contributor.get("first_seen_at")),
                last_seen_at=_coerce_datetime(contributor.get("last_seen_at")),
                contributions_count=int(contributor.get("contributions_count") or 0),
            )
        )

    for commit_payload in snapshot.commits:
        commit = Commit(
            repository_id=repository.id,
            sha=commit_payload["sha"],
            message=commit_payload["message"],
            author_name=commit_payload.get("author_name"),
            author_email=commit_payload.get("author_email"),
            authored_at=_coerce_datetime(commit_payload.get("authored_at")),
            additions=int(commit_payload.get("additions") or 0),
            deletions=int(commit_payload.get("deletions") or 0),
            files_changed=int(commit_payload.get("files_changed") or 0),
        )
        session.add(commit)
        session.flush()

        for file_payload in commit_payload.get("files", []):
            session.add(
                CommitFile(
                    commit_id=commit.id,
                    path=file_payload["path"],
                    additions=int(file_payload.get("additions") or 0),
                    deletions=int(file_payload.get("deletions") or 0),
                )
            )
