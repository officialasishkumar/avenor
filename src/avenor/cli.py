from __future__ import annotations

import subprocess
import sys
from typing import Optional

import typer
import uvicorn

from avenor.config import get_settings
from avenor.db import init_db, session_scope
from avenor.services.repositories import add_repository, list_repositories
from avenor.services.sync import sync_repository

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("init-db")
def init_db_command() -> None:
    """Create the local database schema."""
    init_db()
    typer.echo("Database initialized.")


@app.command("add-repo")
def add_repo_command(url: str) -> None:
    """Add a GitHub repository URL or local git path to the catalog."""
    init_db()
    with session_scope() as session:
        repository = add_repository(session, url)
        typer.echo(f"Added repository {repository.full_name} (id={repository.id}).")


@app.command("list-repos")
def list_repos_command() -> None:
    """List tracked repositories."""
    init_db()
    with session_scope() as session:
        repos = list_repositories(session)
        if not repos:
            typer.echo("No repositories tracked yet. Use 'avenor add-repo <url>' to add one.")
            return
        typer.echo(f"{'ID':<6} {'Repository':<40} {'Status':<10} {'Last Synced'}")
        typer.echo("-" * 80)
        for r in repos:
            synced = r.last_synced_at.strftime("%Y-%m-%d %H:%M") if r.last_synced_at else "never"
            typer.echo(f"{r.id:<6} {r.full_name:<40} {r.sync_status:<10} {synced}")


@app.command("sync")
def sync_command(
    repository_id: Optional[int] = typer.Option(None, "--repo-id"),
    background: bool = typer.Option(False, "--bg", help="Queue via Celery instead of running inline"),
) -> None:
    """Synchronize one repository or all repositories."""
    init_db()

    if background:
        try:
            from avenor.tasks.collection import sync_all_repos, sync_repo
            if repository_id is not None:
                result = sync_repo.delay(repository_id)
                typer.echo(f"Queued sync task: {result.id}")
            else:
                result = sync_all_repos.delay()
                typer.echo(f"Queued sync-all task: {result.id}")
            return
        except Exception as exc:
            typer.echo(f"Celery not available ({exc}), falling back to inline sync.")

    with session_scope() as session:
        repositories = list_repositories(session)
        if repository_id is not None:
            repositories = [r for r in repositories if r.id == repository_id]

        if not repositories:
            raise typer.BadParameter("No repositories available to sync.")

        for repository in repositories:
            typer.echo(f"Synchronizing {repository.full_name}...")
            sync_repository(session, repository)
            typer.echo(f"Synchronized {repository.full_name}.")


@app.command("serve")
def serve_command(
    host: Optional[str] = typer.Option(None, "--host"),
    port: Optional[int] = typer.Option(None, "--port"),
) -> None:
    """Run the web application."""
    settings = get_settings()
    init_db()
    uvicorn.run(
        "avenor.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
        factory=False,
    )


@app.command("worker")
def worker_command(
    concurrency: int = typer.Option(2, "--concurrency", "-c"),
    loglevel: str = typer.Option("info", "--loglevel", "-l"),
) -> None:
    """Start a Celery background worker for data collection."""
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "avenor.tasks",
        "worker",
        "-l", loglevel,
        "-Q", "default,collection",
        "-c", str(concurrency),
    ]
    typer.echo(f"Starting Celery worker (concurrency={concurrency})...")
    subprocess.run(cmd, check=False)


@app.command("quickstart")
def quickstart_command(url: str) -> None:
    """Initialize the database, add one repo, and synchronize it."""
    init_db()
    with session_scope() as session:
        repository = add_repository(session, url)
        typer.echo(f"Added {repository.full_name}, starting sync...")
        sync_repository(session, repository)
        typer.echo(f"Ready: {repository.full_name}")
        typer.echo(f"Run 'avenor serve' to view the dashboard.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
