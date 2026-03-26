from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from avenor.db import init_db, session_scope
from avenor.services.metrics import (
    get_activity_series,
    get_commit_domain_breakdown,
    get_language_breakdown,
    get_new_contributors_series,
    get_overview,
    get_top_contributors,
)
from avenor.services.repositories import add_repository, get_repository, list_repositories
from avenor.services.sync import sync_repository


def create_app() -> FastAPI:
    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))

    app = FastAPI(title="Avenor")
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")

    @app.on_event("startup")
    def startup() -> None:
        init_db()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/repos")
    def api_repos() -> list[dict[str, Any]]:
        with session_scope() as session:
            return [
                {
                    "id": repository.id,
                    "full_name": repository.full_name,
                    "url": repository.url,
                    "sync_status": repository.sync_status,
                    "last_synced_at": repository.last_synced_at.isoformat() if repository.last_synced_at else None,
                }
                for repository in list_repositories(session)
            ]

    @app.get("/")
    def home(request: Request, error: str | None = None):
        with session_scope() as session:
            repositories = list_repositories(session)
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "repositories": repositories,
                "selected_repository": None,
                "page_title": "Repositories",
                "page_name": "home",
                "error": error,
            },
        )

    @app.post("/repos")
    def create_repository(repo_url: str = Form(...)) -> RedirectResponse:
        try:
            with session_scope() as session:
                repository = add_repository(session, repo_url)
                target = f"/repos/{repository.id}/overview"
        except ValueError as exc:
            target = f"/?error={str(exc)}"
        return RedirectResponse(target, status_code=303)

    @app.post("/repos/{repository_id}/sync")
    def sync_repository_route(repository_id: int, request: Request) -> RedirectResponse:
        referrer = request.headers.get("referer", f"/repos/{repository_id}/overview")
        with session_scope() as session:
            repository = get_repository(session, repository_id)
            if repository is None:
                return RedirectResponse("/", status_code=303)
            sync_repository(session, repository)
        return RedirectResponse(referrer, status_code=303)

    @app.get("/repos/{repository_id}")
    def repo_root(repository_id: int) -> RedirectResponse:
        return RedirectResponse(f"/repos/{repository_id}/overview", status_code=303)

    @app.get("/repos/{repository_id}/overview")
    def repo_overview(request: Request, repository_id: int):
        with session_scope() as session:
            repository = get_repository(session, repository_id)
            if repository is None:
                return RedirectResponse("/", status_code=303)
            overview = get_overview(session, repository_id)
            activity = get_activity_series(session, repository_id)
            languages = get_language_breakdown(session, repository_id)
            repositories = list_repositories(session)

        return templates.TemplateResponse(
            "repo_overview.html",
            {
                "request": request,
                "repositories": repositories,
                "selected_repository": repository,
                "page_title": "Overview",
                "page_name": "overview",
                "overview": overview,
                "activity_chart": _line_chart(
                    "Repository Activity",
                    {
                        "Commits": activity["commits"],
                        "Issues": activity["issues"],
                        "Pull Requests": activity["pull_requests"],
                    },
                ),
                "languages_chart": _pie_chart("Languages", languages),
            },
        )

    @app.get("/repos/{repository_id}/contributions")
    def repo_contributions(request: Request, repository_id: int):
        with session_scope() as session:
            repository = get_repository(session, repository_id)
            if repository is None:
                return RedirectResponse("/", status_code=303)
            activity = get_activity_series(session, repository_id)
            domains = get_commit_domain_breakdown(session, repository_id)
            repositories = list_repositories(session)

        return templates.TemplateResponse(
            "repo_contributions.html",
            {
                "request": request,
                "repositories": repositories,
                "selected_repository": repository,
                "page_title": "Contributions",
                "page_name": "contributions",
                "activity_chart": _line_chart(
                    "Contribution Activity",
                    {
                        "Commits": activity["commits"],
                        "Issues": activity["issues"],
                        "Pull Requests": activity["pull_requests"],
                    },
                ),
                "domains_chart": _bar_chart("Commit Email Domains", domains),
            },
        )

    @app.get("/repos/{repository_id}/contributors")
    def repo_contributors(request: Request, repository_id: int):
        with session_scope() as session:
            repository = get_repository(session, repository_id)
            if repository is None:
                return RedirectResponse("/", status_code=303)
            top_contributors = get_top_contributors(session, repository_id)
            new_contributors = get_new_contributors_series(session, repository_id)
            repositories = list_repositories(session)

        return templates.TemplateResponse(
            "repo_contributors.html",
            {
                "request": request,
                "repositories": repositories,
                "selected_repository": repository,
                "page_title": "Contributors",
                "page_name": "contributors",
                "top_contributors": top_contributors,
                "contributors_chart": _bar_chart("Top Contributors", top_contributors),
                "new_contributors_chart": _line_chart(
                    "New Contributors Over Time",
                    {"New Contributors": new_contributors},
                ),
            },
        )

    return app


def _line_chart(title: str, series_map: dict[str, list[dict[str, Any]]]) -> str:
    fig = go.Figure()
    for series_name, rows in series_map.items():
        fig.add_trace(
            go.Scatter(
                x=[row["label"] for row in rows],
                y=[row["value"] for row in rows],
                mode="lines+markers",
                name=series_name,
            )
        )
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _bar_chart(title: str, rows: list[dict[str, Any]]) -> str:
    fig = go.Figure(
        data=[
            go.Bar(
                x=[row["label"] for row in rows],
                y=[row["value"] for row in rows],
                marker_color="#38bdf8",
            )
        ]
    )
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin={"l": 40, "r": 20, "t": 50, "b": 80},
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _pie_chart(title: str, rows: list[dict[str, Any]]) -> str:
    fig = go.Figure(
        data=[
            go.Pie(
                labels=[row["label"] for row in rows],
                values=[row["value"] for row in rows],
                hole=0.45,
            )
        ]
    )
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)
