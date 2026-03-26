"""Avenor web application — FastAPI with Jinja2 templates and REST API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from avenor.config import get_github_token, get_settings, load_ui_settings, save_ui_settings
from avenor.db import init_db, session_scope
from avenor.services.metrics import (
    get_activity_series,
    get_bus_factor,
    get_code_churn_series,
    get_commit_domain_breakdown,
    get_comparison_stats,
    get_contributor_activity_heatmap,
    get_contributor_types,
    get_domain_activity_series,
    get_file_type_breakdown,
    get_hotspot_files,
    get_issue_activity_series,
    get_issue_staleness,
    get_issue_stats,
    get_language_breakdown,
    get_new_contributors_series,
    get_overview,
    get_pr_activity_series,
    get_pr_merge_time_series,
    get_pr_size_distribution,
    get_pr_stats,
    get_release_cadence,
    get_top_contributors,
    get_top_issue_authors,
    get_top_pr_authors,
)
from avenor.services.repositories import (
    add_repository,
    delete_repository,
    get_repository,
    list_repositories,
)
from avenor.services.sync import sync_repository

# Plotly color palette
COLORS = ["#38bdf8", "#818cf8", "#f472b6", "#34d399", "#fbbf24", "#fb923c", "#a78bfa", "#22d3ee"]

VALID_PERIODS = {"day", "week", "month"}


def _validated_period(period: str | None) -> str:
    if period and period in VALID_PERIODS:
        return period
    return "month"


class AddRepoRequest(BaseModel):
    url: str
    auto_sync: bool = False


def create_app() -> FastAPI:
    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    init_db()

    app = FastAPI(title="Avenor", description="Open-source analytics platform")
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")

    # -------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # -------------------------------------------------------------------
    # JSON API — Repository management
    # -------------------------------------------------------------------

    @app.get("/api/repos")
    def api_repos() -> list[dict[str, Any]]:
        with session_scope() as session:
            return [
                {
                    "id": r.id,
                    "full_name": r.full_name,
                    "url": r.url,
                    "description": r.description,
                    "stars": r.stars,
                    "forks": r.forks,
                    "primary_language": r.primary_language,
                    "sync_status": r.sync_status,
                    "sync_error": r.sync_error,
                    "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
                }
                for r in list_repositories(session)
            ]

    @app.post("/api/repos")
    def api_add_repo(body: AddRepoRequest):
        try:
            with session_scope() as session:
                repo = add_repository(session, body.url)
                repo_data = {
                    "id": repo.id,
                    "full_name": repo.full_name,
                    "url": repo.url,
                    "sync_status": repo.sync_status,
                }
            if body.auto_sync:
                try:
                    from avenor.tasks.collection import sync_repo
                    result = sync_repo.delay(repo_data["id"])
                    repo_data["sync_task_id"] = result.id
                    repo_data["sync_status"] = "queued"
                except Exception:
                    with session_scope() as session:
                        r = get_repository(session, repo_data["id"])
                        if r:
                            sync_repository(session, r)
                            repo_data["sync_status"] = "ready"
            return repo_data
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.delete("/api/repos/{repository_id}")
    def api_delete_repo(repository_id: int):
        with session_scope() as session:
            deleted = delete_repository(session, repository_id)
        if not deleted:
            return JSONResponse({"error": "Repository not found"}, status_code=404)
        return {"status": "deleted", "id": repository_id}

    @app.get("/api/repos/{repository_id}/status")
    def api_repo_status(repository_id: int):
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return JSONResponse({"error": "Repository not found"}, status_code=404)
            return {
                "id": repo.id,
                "full_name": repo.full_name,
                "sync_status": repo.sync_status,
                "sync_error": repo.sync_error,
                "last_synced_at": repo.last_synced_at.isoformat() if repo.last_synced_at else None,
            }

    @app.post("/api/repos/{repository_id}/sync")
    def api_sync(repository_id: int):
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return JSONResponse({"error": "Repository not found"}, status_code=404)
            if repo.sync_status == "running":
                return {"status": "already_running", "id": repository_id}
        try:
            from avenor.tasks.collection import sync_repo
            result = sync_repo.delay(repository_id)
            return {"task_id": result.id, "status": "queued"}
        except Exception:
            with session_scope() as session:
                repo = get_repository(session, repository_id)
                if repo is None:
                    return JSONResponse({"error": "Repository not found"}, status_code=404)
                sync_repository(session, repo)
                return {"status": "completed"}

    # -------------------------------------------------------------------
    # JSON API — Settings
    # -------------------------------------------------------------------

    @app.get("/api/settings")
    def api_get_settings():
        ui = load_ui_settings()
        token = get_github_token()
        return {
            "github_token_configured": bool(token),
            "github_token_source": "environment" if os.getenv("AVENOR_GITHUB_TOKEN") else ("ui" if ui.get("github_token") else None),
            "github_token_masked": f"ghp_...{token[-4:]}" if token and len(token) > 8 else ("***" if token else None),
            "data_dir": str(get_settings().data_dir),
        }

    class SaveSettingsRequest(BaseModel):
        github_token: str | None = None

    @app.post("/api/settings")
    def api_save_settings(body: SaveSettingsRequest):
        ui = load_ui_settings()
        if body.github_token is not None:
            token = body.github_token.strip()
            if token:
                ui["github_token"] = token
            else:
                ui.pop("github_token", None)
        save_ui_settings(ui)
        return {"status": "saved"}

    # -------------------------------------------------------------------
    # JSON API — Sync All
    # -------------------------------------------------------------------

    @app.post("/api/repos/sync-all")
    def api_sync_all():
        with session_scope() as session:
            repos = list_repositories(session)
            if not repos:
                return {"status": "no_repos", "synced": 0}
            results = []
            for repo in repos:
                if repo.sync_status == "running":
                    results.append({"id": repo.id, "status": "already_running"})
                    continue
                try:
                    from avenor.tasks.collection import sync_repo
                    sync_repo.delay(repo.id)
                    results.append({"id": repo.id, "status": "queued"})
                except Exception:
                    results.append({"id": repo.id, "status": "inline_pending"})
        # Inline fallback for repos that couldn't be queued
        for r in results:
            if r["status"] == "inline_pending":
                try:
                    with session_scope() as session:
                        repo = get_repository(session, r["id"])
                        if repo:
                            sync_repository(session, repo)
                    r["status"] = "completed"
                except Exception as exc:
                    r["status"] = f"failed: {exc}"
        return {"status": "ok", "results": results}

    # -------------------------------------------------------------------
    # JSON API — Metrics
    # -------------------------------------------------------------------

    @app.get("/api/repos/{repository_id}/overview")
    def api_overview(repository_id: int):
        with session_scope() as session:
            ov = get_overview(session, repository_id)
            return {k: v for k, v in ov.items() if k not in ("repository", "recent_releases")}

    @app.get("/api/repos/{repository_id}/activity")
    def api_activity(repository_id: int, period: str = "month"):
        with session_scope() as session:
            return get_activity_series(session, repository_id, _validated_period(period))

    @app.get("/api/repos/{repository_id}/contributors")
    def api_contributors(repository_id: int, limit: int = 15):
        with session_scope() as session:
            return get_top_contributors(session, repository_id, limit)

    @app.get("/api/repos/{repository_id}/contributor-types")
    def api_contributor_types(repository_id: int):
        with session_scope() as session:
            return get_contributor_types(session, repository_id)

    @app.get("/api/repos/{repository_id}/bus-factor")
    def api_bus_factor(repository_id: int):
        with session_scope() as session:
            return get_bus_factor(session, repository_id)

    @app.get("/api/repos/{repository_id}/issues/stats")
    def api_issue_stats(repository_id: int):
        with session_scope() as session:
            return get_issue_stats(session, repository_id)

    @app.get("/api/repos/{repository_id}/prs/stats")
    def api_pr_stats(repository_id: int):
        with session_scope() as session:
            return get_pr_stats(session, repository_id)

    @app.get("/api/repos/{repository_id}/heatmap")
    def api_heatmap(repository_id: int):
        with session_scope() as session:
            return get_contributor_activity_heatmap(session, repository_id)

    @app.get("/api/repos/{repository_id}/hotspots")
    def api_hotspots(repository_id: int, limit: int = 20):
        with session_scope() as session:
            return get_hotspot_files(session, repository_id, limit)

    @app.get("/api/compare")
    def api_compare(ids: str = Query(...)):
        repo_ids = [int(x) for x in ids.split(",") if x.strip()]
        with session_scope() as session:
            return get_comparison_stats(session, repo_ids)

    # -------------------------------------------------------------------
    # HTML pages
    # -------------------------------------------------------------------

    def _common_ctx(request: Request, session, selected_repo=None, page_name="home", page_title="Avenor"):
        repos = list_repositories(session)
        return {
            "request": request,
            "repositories": repos,
            "selected_repository": selected_repo,
            "page_name": page_name,
            "page_title": page_title,
        }

    @app.get("/")
    def home(request: Request, error: str | None = None):
        with session_scope() as session:
            repos = list_repositories(session)
            comparison = []
            if len(repos) >= 2:
                comparison = get_comparison_stats(session, [r.id for r in repos])

        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={
                "request": request,
                "repositories": repos,
                "selected_repository": None,
                "page_title": "Dashboard",
                "page_name": "home",
                "error": error,
                "comparison": comparison,
                "comparison_chart": _comparison_chart(comparison) if comparison else "",
            },
        )

    @app.post("/repos")
    def create_repository(repo_url: str = Form(...)) -> RedirectResponse:
        try:
            with session_scope() as session:
                repo = add_repository(session, repo_url)
                target = f"/repos/{repo.id}/overview"
        except ValueError as exc:
            target = f"/?error={str(exc)}"
        return RedirectResponse(target, status_code=303)

    @app.post("/repos/{repository_id}/sync")
    def sync_repository_route(repository_id: int, request: Request) -> RedirectResponse:
        referrer = request.headers.get("referer", f"/repos/{repository_id}/overview")
        try:
            from avenor.tasks.collection import sync_repo
            sync_repo.delay(repository_id)
        except Exception:
            with session_scope() as session:
                repo = get_repository(session, repository_id)
                if repo:
                    sync_repository(session, repo)
        return RedirectResponse(referrer, status_code=303)

    @app.get("/repos/{repository_id}")
    def repo_root(repository_id: int) -> RedirectResponse:
        return RedirectResponse(f"/repos/{repository_id}/overview", status_code=303)

    # -- Overview --
    @app.get("/repos/{repository_id}/overview")
    def repo_overview(request: Request, repository_id: int, period: str | None = None):
        p = _validated_period(period)
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return RedirectResponse("/", status_code=303)
            overview = get_overview(session, repository_id)
            activity = get_activity_series(session, repository_id, p)
            languages = get_language_breakdown(session, repository_id)
            bus = get_bus_factor(session, repository_id)
            contributor_types = get_contributor_types(session, repository_id)
            ctx = _common_ctx(request, session, repo, "overview", "Overview")

        ctx.update({
            "period": p,
            "overview": overview,
            "bus_factor": bus,
            "contributor_types": contributor_types,
            "activity_chart": _multi_line_chart("Repository Activity", activity),
            "languages_chart": _donut_chart("Languages", languages),
            "contributor_types_chart": _donut_chart("Contributor Types", [
                {"label": "Drive-by (1)", "value": contributor_types["drive_by"]},
                {"label": "Repeat (2-10)", "value": contributor_types["repeat"]},
                {"label": "Core (10+)", "value": contributor_types["core"]},
            ]),
        })
        return templates.TemplateResponse(request=request, name="repo_overview.html", context=ctx)

    # -- Contributions --
    @app.get("/repos/{repository_id}/contributions")
    def repo_contributions(request: Request, repository_id: int, period: str | None = None):
        p = _validated_period(period)
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return RedirectResponse("/", status_code=303)
            activity = get_activity_series(session, repository_id, p)
            domains = get_commit_domain_breakdown(session, repository_id)
            churn = get_code_churn_series(session, repository_id, p)
            heatmap_data = get_contributor_activity_heatmap(session, repository_id)
            ctx = _common_ctx(request, session, repo, "contributions", "Contributions")

        ctx.update({
            "period": p,
            "activity_chart": _multi_line_chart("Contribution Activity", activity),
            "domains_chart": _horizontal_bar_chart("Commit Email Domains", domains),
            "churn_chart": _area_chart("Code Churn (Lines Changed)", churn),
            "heatmap_chart": _heatmap_chart("Commit Activity Heatmap", heatmap_data),
        })
        return templates.TemplateResponse(request=request, name="repo_contributions.html", context=ctx)

    # -- Contributors --
    @app.get("/repos/{repository_id}/contributors")
    def repo_contributors(request: Request, repository_id: int, period: str | None = None):
        p = _validated_period(period)
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return RedirectResponse("/", status_code=303)
            top = get_top_contributors(session, repository_id)
            new_contribs = get_new_contributors_series(session, repository_id, p)
            types = get_contributor_types(session, repository_id)
            bus = get_bus_factor(session, repository_id)
            domain_series = get_domain_activity_series(session, repository_id, period=p)
            ctx = _common_ctx(request, session, repo, "contributors", "Contributors")

        ctx.update({
            "period": p,
            "top_contributors": top,
            "contributor_types": types,
            "bus_factor": bus,
            "contributors_chart": _horizontal_bar_chart("Top Contributors", top),
            "new_contributors_chart": _area_chart("New Contributors Over Time", new_contribs),
            "domain_series_chart": _multi_line_chart("Activity by Email Domain", domain_series),
        })
        return templates.TemplateResponse(request=request, name="repo_contributors.html", context=ctx)

    # -- Issues --
    @app.get("/repos/{repository_id}/issues")
    def repo_issues(request: Request, repository_id: int, period: str | None = None):
        p = _validated_period(period)
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return RedirectResponse("/", status_code=303)
            stats = get_issue_stats(session, repository_id)
            activity = get_issue_activity_series(session, repository_id, p)
            staleness = get_issue_staleness(session, repository_id)
            top_authors = get_top_issue_authors(session, repository_id)
            ctx = _common_ctx(request, session, repo, "issues", "Issues")

        ctx.update({
            "period": p,
            "stats": stats,
            "activity_chart": _multi_line_chart("Issues Opened vs Closed", activity),
            "staleness_chart": _donut_chart("Open Issue Staleness", staleness),
            "authors_chart": _horizontal_bar_chart("Top Issue Authors", top_authors),
        })
        return templates.TemplateResponse(request=request, name="repo_issues.html", context=ctx)

    # -- Pull Requests --
    @app.get("/repos/{repository_id}/pull-requests")
    def repo_prs(request: Request, repository_id: int, period: str | None = None):
        p = _validated_period(period)
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return RedirectResponse("/", status_code=303)
            stats = get_pr_stats(session, repository_id)
            activity = get_pr_activity_series(session, repository_id, p)
            size_dist = get_pr_size_distribution(session, repository_id)
            merge_times = get_pr_merge_time_series(session, repository_id, p)
            top_authors = get_top_pr_authors(session, repository_id)
            ctx = _common_ctx(request, session, repo, "pull_requests", "Pull Requests")

        ctx.update({
            "period": p,
            "stats": stats,
            "activity_chart": _multi_line_chart("PR Activity", activity),
            "size_chart": _bar_chart("PR Size Distribution", size_dist),
            "merge_time_chart": _area_chart("Average Merge Time (hours)", merge_times),
            "authors_chart": _horizontal_bar_chart("Top PR Authors", top_authors),
        })
        return templates.TemplateResponse(request=request, name="repo_prs.html", context=ctx)

    # -- Codebase --
    @app.get("/repos/{repository_id}/codebase")
    def repo_codebase(request: Request, repository_id: int, period: str | None = None):
        p = _validated_period(period)
        with session_scope() as session:
            repo = get_repository(session, repository_id)
            if repo is None:
                return RedirectResponse("/", status_code=303)
            hotspots = get_hotspot_files(session, repository_id)
            churn = get_code_churn_series(session, repository_id, p)
            file_types = get_file_type_breakdown(session, repository_id)
            release_cadence = get_release_cadence(session, repository_id)
            ctx = _common_ctx(request, session, repo, "codebase", "Codebase")

        ctx.update({
            "period": p,
            "hotspots": hotspots,
            "churn_chart": _area_chart("Code Churn Over Time", churn),
            "file_types_chart": _donut_chart("File Types Changed", file_types),
            "hotspot_chart": _horizontal_bar_chart("Most Changed Files", hotspots[:15]),
            "release_cadence_chart": _bar_chart("Days Between Releases", release_cadence) if release_cadence else "",
        })
        return templates.TemplateResponse(request=request, name="repo_codebase.html", context=ctx)

    # -- Settings --
    @app.get("/settings")
    def settings_page(request: Request):
        ui = load_ui_settings()
        token = get_github_token()
        with session_scope() as session:
            ctx = _common_ctx(request, session, page_name="settings", page_title="Settings")
        ctx.update({
            "github_token_configured": bool(token),
            "github_token_source": "environment" if os.getenv("AVENOR_GITHUB_TOKEN") else ("ui" if ui.get("github_token") else None),
            "github_token_masked": f"ghp_...{token[-4:]}" if token and len(token) > 8 else ("***" if token else None),
            "data_dir": str(get_settings().data_dir),
            "database_url": get_settings().database_url,
            "redis_url": get_settings().redis_url,
        })
        return templates.TemplateResponse(request=request, name="settings.html", context=ctx)

    return app


# ---------------------------------------------------------------------------
# Chart helpers — Plotly → HTML fragments with dark theme
# ---------------------------------------------------------------------------

_LAYOUT_BASE = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="IBM Plex Sans, sans-serif", color="#e5eefb"),
    margin=dict(l=50, r=20, t=45, b=45),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def _multi_line_chart(title: str, series_map: dict[str, list[dict[str, Any]]]) -> str:
    fig = go.Figure()
    for idx, (name, rows) in enumerate(series_map.items()):
        color = COLORS[idx % len(COLORS)]
        fig.add_trace(go.Scatter(
            x=[r["label"] for r in rows],
            y=[r["value"] for r in rows],
            mode="lines+markers",
            name=name.replace("_", " ").title(),
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))
    fig.update_layout(title=title, **_LAYOUT_BASE)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _area_chart(title: str, rows: list[dict[str, Any]]) -> str:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r["label"] for r in rows],
        y=[r["value"] for r in rows],
        fill="tozeroy",
        line=dict(color=COLORS[0], width=2),
        fillcolor="rgba(56,189,248,0.15)",
    ))
    fig.update_layout(title=title, showlegend=False, **_LAYOUT_BASE)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _bar_chart(title: str, rows: list[dict[str, Any]]) -> str:
    fig = go.Figure(data=[go.Bar(
        x=[r["label"] for r in rows],
        y=[r["value"] for r in rows],
        marker_color=COLORS[0],
        marker_line=dict(width=0),
    )])
    fig.update_layout(title=title, showlegend=False, **_LAYOUT_BASE)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _horizontal_bar_chart(title: str, rows: list[dict[str, Any]]) -> str:
    reversed_rows = list(reversed(rows))
    fig = go.Figure(data=[go.Bar(
        x=[r["value"] for r in reversed_rows],
        y=[r["label"] for r in reversed_rows],
        orientation="h",
        marker_color=COLORS[0],
        marker_line=dict(width=0),
    )])
    layout = {**_LAYOUT_BASE, "margin": dict(l=180, r=20, t=45, b=45)}
    fig.update_layout(title=title, showlegend=False, **layout)
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _donut_chart(title: str, rows: list[dict[str, Any]]) -> str:
    fig = go.Figure(data=[go.Pie(
        labels=[r["label"] for r in rows],
        values=[r["value"] for r in rows],
        hole=0.5,
        marker=dict(colors=COLORS[:len(rows)]),
        textinfo="label+percent",
        textposition="outside",
    )])
    fig.update_layout(title=title, showlegend=False, **_LAYOUT_BASE)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _heatmap_chart(title: str, data: list[dict[str, Any]]) -> str:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hours = list(range(24))
    z = [[0] * 24 for _ in range(7)]
    for d in data:
        day_idx = days.index(d["day"])
        z[day_idx][d["hour"]] = d["value"]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=[f"{h:02d}:00" for h in hours],
        y=days,
        colorscale=[[0, "rgba(9,17,31,0.8)"], [0.5, "#38bdf8"], [1, "#f472b6"]],
        showscale=True,
    ))
    fig.update_layout(title=title, **_LAYOUT_BASE)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _comparison_chart(data: list[dict[str, Any]]) -> str:
    names = [d["full_name"] for d in data]
    fig = go.Figure()
    for metric, color in [("commits", COLORS[0]), ("pull_requests", COLORS[1]), ("issues", COLORS[2])]:
        fig.add_trace(go.Bar(
            name=metric.replace("_", " ").title(),
            x=names,
            y=[d[metric] for d in data],
            marker_color=color,
        ))
    fig.update_layout(
        title="Repository Comparison",
        barmode="group",
        **_LAYOUT_BASE,
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
