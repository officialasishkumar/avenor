# Avenor

**Unified open-source analytics platform** — combines the data collection power of [Augur](https://github.com/chaoss/augur) with the rich visualizations of [8knot](https://github.com/rit-sse/8knot) into a single project.

## Features

- **Data Collection**: GitHub API + git log parsing with background task queue (Celery + Redis)
- **20+ CHAOSS-Inspired Metrics**: Bus factor, contributor types, PR merge times, issue staleness, code churn, domain affiliation, and more
- **6-Page Analytics Dashboard**: Overview, Contributions, Contributors, Issues, Pull Requests, Codebase
- **Interactive Plotly Charts**: Heatmaps, area charts, donut charts, horizontal bars, multi-line time series
- **Full REST API**: JSON endpoints for all metrics at `/api/repos/{id}/*`
- **Multi-Repo Comparison**: Side-by-side repository metrics on the home dashboard
- **Docker Compose**: One-command deployment with app, Celery worker, Redis, PostgreSQL, and Flower monitoring
- **CLI**: `avenor quickstart <url>` to go from zero to dashboard in one command

## Quick Start (Local)

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# One command to init, add, sync, and be ready:
.venv/bin/avenor quickstart https://github.com/chaoss/augur

# Start the dashboard:
.venv/bin/avenor serve
# Open http://127.0.0.1:8000
```

## Quick Start (Docker)

```bash
# Set your GitHub token for higher API rate limits
export AVENOR_GITHUB_TOKEN=ghp_your_token_here

# Start all services
docker compose up -d

# Open http://localhost:8000
```

This starts: web app (port 8000), Celery worker, Redis, PostgreSQL, and Flower (port 5555).

## CLI Commands

```bash
avenor init-db                    # Create database schema
avenor add-repo <url>             # Track a GitHub URL or local git path
avenor list-repos                 # Show tracked repositories
avenor sync [--repo-id ID]        # Sync data (inline)
avenor sync --bg                  # Sync via Celery background worker
avenor serve [--host] [--port]    # Start web dashboard
avenor worker [-c 2]              # Start Celery background worker
avenor quickstart <url>           # Init + add + sync in one command
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/repos` | List all tracked repositories |
| `GET /api/repos/{id}/overview` | Key stats (commits, PRs, issues, merge rate) |
| `GET /api/repos/{id}/activity` | Activity time series |
| `GET /api/repos/{id}/contributors` | Top contributors |
| `GET /api/repos/{id}/contributor-types` | Drive-by / repeat / core breakdown |
| `GET /api/repos/{id}/bus-factor` | Bus factor calculation |
| `GET /api/repos/{id}/issues/stats` | Issue close rate, median close time |
| `GET /api/repos/{id}/prs/stats` | PR merge rate, median merge time |
| `GET /api/repos/{id}/heatmap` | Commit activity heatmap (day x hour) |
| `GET /api/repos/{id}/hotspots` | Most frequently changed files |
| `GET /api/compare?ids=1,2,3` | Multi-repo comparison |
| `POST /api/repos/{id}/sync` | Trigger background sync |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Avenor                           │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌────────────────┐  │
│  │ FastAPI  │   │  Celery  │   │  Collectors    │  │
│  │ Web UI   │◄──│  Worker  │──►│  GitHub + Git  │  │
│  │ REST API │   │          │   │                │  │
│  └────┬─────┘   └────┬─────┘   └────────────────┘  │
│       │              │                              │
│  ┌────▼──────────────▼──────┐   ┌──────────────┐   │
│  │    SQLAlchemy ORM        │   │    Redis      │   │
│  │  SQLite / PostgreSQL     │   │  Broker +     │   │
│  │                          │   │  Backend      │   │
│  └──────────────────────────┘   └──────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AVENOR_DATA_DIR` | `./.avenor` | Data directory for SQLite and cloned repos |
| `AVENOR_DATABASE_URL` | `sqlite:///.avenor/avenor.db` | Database connection string |
| `AVENOR_GITHUB_TOKEN` | *(none)* | GitHub API token for higher rate limits |
| `AVENOR_REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery |
| `AVENOR_HOST` | `127.0.0.1` | Web server host |
| `AVENOR_PORT` | `8000` | Web server port |

## Dashboard Pages

- **Home**: Repository listing, multi-repo comparison chart and table
- **Overview**: Key stats, activity timeline, language pie chart, contributor types, recent releases
- **Contributions**: Commit activity, code churn, email domain breakdown, commit heatmap
- **Contributors**: Top contributors, new contributor growth, bus factor, domain activity
- **Issues**: Open/closed stats, close rate, median close time, staleness, top authors
- **Pull Requests**: Merge rate, merge time trends, PR size distribution, code impact
- **Codebase**: File hotspots, code churn over time, file type distribution, release cadence

## Running Tests

```bash
.venv/bin/pytest tests/ -v
```
