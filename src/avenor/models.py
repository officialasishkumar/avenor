from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from avenor.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host: Mapped[str] = mapped_column(String(255), default="github.com")
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(511), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    homepage_url: Mapped[str | None] = mapped_column(String(1024))
    default_branch: Mapped[str | None] = mapped_column(String(255))
    primary_language: Mapped[str | None] = mapped_column(String(255))
    languages: Mapped[dict[str, int] | None] = mapped_column(JSON)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(default=False)
    external_id: Mapped[int | None] = mapped_column(Integer, index=True)
    sync_status: Mapped[str] = mapped_column(String(64), default="idle", index=True)
    sync_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    collection_jobs: Mapped[list["CollectionJob"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    contributors: Mapped[list["Contributor"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    issues: Mapped[list["Issue"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    releases: Mapped[list["Release"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    commits: Mapped[list["Commit"]] = relationship(back_populates="repository", cascade="all, delete-orphan")


class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    __table_args__ = (UniqueConstraint("repository_id", "collector", name="uq_collection_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    collector: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), default="idle", index=True)
    cursor: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository: Mapped["Repository"] = relationship(back_populates="collection_jobs")
    job_runs: Mapped[list["JobRun"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("collection_jobs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(64), default="running", index=True)
    records_written: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped["CollectionJob"] = relationship(back_populates="job_runs")


class Contributor(Base):
    __tablename__ = "contributors"
    __table_args__ = (UniqueConstraint("repository_id", "source", "external_id", name="uq_contributor_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(64), default="github")
    external_id: Mapped[str | None] = mapped_column(String(255))
    login: Mapped[str | None] = mapped_column(String(255), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributions_count: Mapped[int] = mapped_column(Integer, default=0)

    repository: Mapped["Repository"] = relationship(back_populates="contributors")


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("repository_id", "external_id", name="uq_issue_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(64), index=True)
    author_login: Mapped[str | None] = mapped_column(String(255), index=True)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository: Mapped["Repository"] = relationship(back_populates="issues")


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("repository_id", "external_id", name="uq_pr_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(64), index=True)
    author_login: Mapped[str | None] = mapped_column(String(255), index=True)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    review_comments_count: Mapped[int] = mapped_column(Integer, default=0)
    commits_count: Mapped[int] = mapped_column(Integer, default=0)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    changed_files: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository: Mapped["Repository"] = relationship(back_populates="pull_requests")


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (UniqueConstraint("repository_id", "external_id", name="uq_release_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    tag_name: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    draft: Mapped[bool] = mapped_column(default=False)
    prerelease: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    repository: Mapped["Repository"] = relationship(back_populates="releases")


class Commit(Base):
    __tablename__ = "commits"
    __table_args__ = (UniqueConstraint("repository_id", "sha", name="uq_commit_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    sha: Mapped[str] = mapped_column(String(255), index=True)
    message: Mapped[str] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(255), index=True)
    author_email: Mapped[str | None] = mapped_column(String(255), index=True)
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)

    repository: Mapped["Repository"] = relationship(back_populates="commits")
    files: Mapped[list["CommitFile"]] = relationship(back_populates="commit", cascade="all, delete-orphan")


class CommitFile(Base):
    __tablename__ = "commit_files"
    __table_args__ = (UniqueConstraint("commit_id", "path", name="uq_commit_file"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commit_id: Mapped[int] = mapped_column(ForeignKey("commits.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(1024), index=True)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)

    commit: Mapped["Commit"] = relationship(back_populates="files")
