from __future__ import annotations

from pathlib import Path

import pytest

from avenor.db import init_db, session_scope
from avenor.services.repositories import add_repository, list_repositories, parse_repository_url


def test_parse_repository_url_normalizes_github_urls() -> None:
    parsed = parse_repository_url("https://github.com/Chaoss/Augur.git")
    assert parsed.host == "github.com"
    assert parsed.owner == "chaoss"
    assert parsed.name == "Augur"
    assert parsed.normalized_url == "https://github.com/chaoss/Augur"


def test_add_repository_deduplicates_by_full_name() -> None:
    init_db()
    with session_scope() as session:
        first = add_repository(session, "https://github.com/chaoss/augur")
        second = add_repository(session, "https://github.com/chaoss/augur.git")
        repositories = list_repositories(session)

    assert first.id == second.id
    assert len(repositories) == 1


def test_add_repository_rejects_non_github_urls() -> None:
    init_db()
    with session_scope() as session:
        with pytest.raises(ValueError):
            add_repository(session, "https://gitlab.com/example/project")


def test_add_repository_accepts_local_git_paths(tmp_path: Path) -> None:
    repo = tmp_path / "demo-repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    init_db()
    with session_scope() as session:
        repository = add_repository(session, str(repo))

    assert repository.host == "local"
    assert repository.url == str(repo.resolve())
