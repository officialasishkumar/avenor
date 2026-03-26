from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from avenor.models import Repository

GITHUB_REPO_RE = re.compile(
    r"^(?:https?://)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)

# Shorthand: owner/repo (no slashes beyond the single separator)
SHORTHAND_RE = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)$",
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
    local_path = Path(candidate).expanduser()
    if local_path.exists() and local_path.is_dir() and (local_path / ".git").exists():
        owner = local_path.parent.name or "workspace"
        name = local_path.name
        return ParsedRepositoryUrl(host="local", owner=owner, name=name)

    match = GITHUB_REPO_RE.match(candidate)
    if match:
        return ParsedRepositoryUrl(
            host="github.com",
            owner=match.group("owner").lower(),
            name=match.group("name").removesuffix(".git"),
        )

    # Accept owner/repo shorthand (e.g. "torvalds/linux")
    shorthand = SHORTHAND_RE.match(candidate)
    if shorthand:
        return ParsedRepositoryUrl(
            host="github.com",
            owner=shorthand.group("owner").lower(),
            name=shorthand.group("name"),
        )

    raise ValueError("Use a GitHub URL (https://github.com/owner/repo), shorthand (owner/repo), or a local git path.")


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

    normalized_url = parsed.normalized_url if parsed.host != "local" else str(Path(url).expanduser().resolve())
    repository = Repository(
        host=parsed.host,
        owner=parsed.owner,
        name=parsed.name,
        full_name=parsed.full_name,
        url=normalized_url,
    )
    session.add(repository)
    session.flush()
    return repository


def delete_repository(session: Session, repository_id: int) -> bool:
    """Delete a repository and all its collected data. Returns True if found."""
    repo = session.get(Repository, repository_id)
    if repo is None:
        return False
    session.delete(repo)
    session.flush()
    return True
