from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from avenor.models import Repository

GITHUB_REPO_RE = re.compile(
    r"^(?:https?://)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedRepositoryUrl:
    host: str
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def normalized_url(self) -> str:
        return f"https://{self.host}/{self.full_name}"


def parse_repository_url(url: str) -> ParsedRepositoryUrl:
    candidate = url.strip()
    match = GITHUB_REPO_RE.match(candidate)
    if not match:
        raise ValueError("Only GitHub repository URLs are supported in the current build.")
    return ParsedRepositoryUrl(
        host="github.com",
        owner=match.group("owner").lower(),
        name=match.group("name").removesuffix(".git"),
    )


def list_repositories(session: Session) -> list[Repository]:
    return list(session.scalars(select(Repository).order_by(Repository.full_name)))


def get_repository(session: Session, repository_id: int) -> Repository | None:
    return session.get(Repository, repository_id)


def get_repository_by_full_name(session: Session, full_name: str) -> Repository | None:
    stmt = select(Repository).where(Repository.full_name == full_name.lower())
    return session.scalars(stmt).first()


def add_repository(session: Session, url: str) -> Repository:
    parsed = parse_repository_url(url)
    existing = get_repository_by_full_name(session, parsed.full_name)
    if existing:
        return existing

    repository = Repository(
        host=parsed.host,
        owner=parsed.owner,
        name=parsed.name,
        full_name=parsed.full_name,
        url=parsed.normalized_url,
    )
    session.add(repository)
    session.flush()
    return repository
