"""Background collection tasks using Celery.

These mirror Augur's phased collection approach:
  1. GitHub metadata collection
  2. Git commit log collection
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from celery import shared_task

from avenor.config import get_settings
from avenor.db import init_db, session_scope

logger = logging.getLogger(__name__)


def _publish_progress(task, repo_full_name: str, phase: str, status: str, detail: str = "") -> None:
    """Update Celery task meta so the frontend can poll progress."""
    task.update_state(
        state="PROGRESS",
        meta={
            "repo": repo_full_name,
            "phase": phase,
            "status": status,
            "detail": detail,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


@shared_task(bind=True, name="avenor.tasks.collection.sync_repo", queue="collection")
def sync_repo(self, repository_id: int) -> dict:
    """Full sync for a single repository — GitHub + Git phases."""
    from avenor.collectors.git import GitCollector
    from avenor.collectors.github import GitHubCollector
    from avenor.models import Repository
    from avenor.services.sync import sync_repository

    init_db()
    settings = get_settings()

    with session_scope() as session:
        repo = session.get(Repository, repository_id)
        if repo is None:
            return {"error": f"Repository {repository_id} not found"}

        repo_name = repo.full_name
        _publish_progress(self, repo_name, "sync", "started")

        try:
            repo.sync_status = "running"
            repo.sync_error = None
            session.flush()

            _publish_progress(self, repo_name, "sync", "collecting")
            sync_repository(session, repo)
            _publish_progress(self, repo_name, "sync", "completed")

            return {
                "repository_id": repository_id,
                "full_name": repo_name,
                "status": "ready",
            }
        except Exception as exc:
            logger.exception("Sync failed for %s", repo_name)
            repo.sync_status = "failed"
            repo.sync_error = str(exc)
            session.flush()
            _publish_progress(self, repo_name, "sync", "failed", str(exc))
            raise


@shared_task(bind=True, name="avenor.tasks.collection.sync_all_repos", queue="collection")
def sync_all_repos(self) -> dict:
    """Queue sync tasks for every tracked repository."""
    from avenor.models import Repository

    init_db()

    with session_scope() as session:
        from avenor.services.repositories import list_repositories

        repos = list_repositories(session)
        task_ids = []
        for repo in repos:
            result = sync_repo.delay(repo.id)
            task_ids.append({"repository_id": repo.id, "task_id": result.id})

    return {"queued": len(task_ids), "tasks": task_ids}
