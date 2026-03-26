from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from avenor.db import init_db, reset_db_state


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    data_dir = tmp_path / ".avenor"
    monkeypatch.setenv("AVENOR_DATA_DIR", data_dir.as_posix())
    reset_db_state()
    init_db()
    yield data_dir
    reset_db_state()


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(["git", "-C", repo.as_posix(), *args], check=True, env=env, capture_output=True, text=True)


@pytest.fixture()
def git_repo(tmp_path) -> Path:
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Default User")
    _git(repo, "config", "user.email", "default@example.com")

    (repo / "main.py").write_text("print('hello')\n", encoding="utf-8")
    env_one = os.environ.copy()
    env_one.update(
        {
            "GIT_AUTHOR_NAME": "Alice",
            "GIT_AUTHOR_EMAIL": "alice@example.com",
            "GIT_COMMITTER_NAME": "Alice",
            "GIT_COMMITTER_EMAIL": "alice@example.com",
        }
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit", env=env_one)

    (repo / "README.md").write_text("# demo\n", encoding="utf-8")
    env_two = os.environ.copy()
    env_two.update(
        {
            "GIT_AUTHOR_NAME": "Bob",
            "GIT_AUTHOR_EMAIL": "bob@example.com",
            "GIT_COMMITTER_NAME": "Bob",
            "GIT_COMMITTER_EMAIL": "bob@example.com",
        }
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "docs update", env=env_two)

    return repo

