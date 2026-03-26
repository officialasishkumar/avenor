from __future__ import annotations

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
    """Add a GitHub repository URL to the local catalog."""
    init_db()
    with session_scope() as session:
        repository = add_repository(session, url)
        typer.echo(f"Added repository {repository.full_name} (id={repository.id}).")


@app.command("list-repos")
def list_repos_command() -> None:
    """List tracked repositories."""
    init_db()
    with session_scope() as session:
        for repository in list_repositories(session):
            typer.echo(f"{repository.id}: {repository.full_name} [{repository.sync_status}]")


@app.command("sync")
def sync_command(repository_id: Optional[int] = typer.Option(None, "--repo-id")) -> None:
    """Synchronize one repository or all repositories."""
    init_db()
    with session_scope() as session:
        repositories = list_repositories(session)
        if repository_id is not None:
            repositories = [repository for repository in repositories if repository.id == repository_id]

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


@app.command("quickstart")
def quickstart_command(url: str) -> None:
    """Initialize the database, add one repo, and synchronize it."""
    init_db()
    with session_scope() as session:
        repository = add_repository(session, url)
        sync_repository(session, repository)
        typer.echo(f"Ready: {repository.full_name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
