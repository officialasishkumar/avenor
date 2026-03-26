# Avenor

**Unified open-source analytics platform** — collection, storage, and visualization in one project.

## Features

- **Data Collection**: GitHub API + git log parsing with background task queue (Celery + Redis)
- **20+ CHAOSS-Inspired Metrics**: Bus factor, contributor types, PR merge times, issue staleness, code churn, domain affiliation, and more
- **6-Page Analytics Dashboard**: Overview, Contributions, Contributors, Issues, Pull Requests, Codebase
- **Interactive Plotly Charts**: Heatmaps, area charts, donut charts, horizontal bars, multi-line time series
- **Full REST API**: JSON endpoints for all metrics at `/api/repos/{id}/*`
- **Multi-Repo Comparison**: Side-by-side repository metrics on the home dashboard
- **Docker Compose**: One-command deployment with app, Celery worker, Redis, PostgreSQL, and Flower monitoring
- **CLI**: `avenor quickstart <url>` to go from zero to dashboard in one command
- **Async UI**: Toast notifications, background sync, sidebar search, mobile navigation
- **Time Period Controls**: Switch between daily, weekly, and monthly chart granularity

## Quick Start (Local)

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# 2. Install
pip install -e '.[dev]'

# 3. One command to init, add, sync, and be ready:
avenor quickstart https://github.com/owner/repo

# 4. Start the dashboard:
avenor serve
# Open http://127.0.0.1:8000
```

### Optional: Set a GitHub token for higher rate limits

```bash
export AVENOR_GITHUB_TOKEN=ghp_your_token_here
```

Without a token you're limited to 60 GitHub API requests/hour. With a token: 5,000/hour.

## Quick Start (Docker)

```bash
# Set your GitHub token (optional but recommended)
export AVENOR_GITHUB_TOKEN=ghp_your_token_here

# Start all services
docker compose up -d

# Open http://localhost:8000
```

This starts: web app (port 8000), Celery worker, Redis, PostgreSQL, and Flower task monitor (port 5555).

## CLI Commands

| Command | Description |
|---------|-------------|
| `avenor init-db` | Create the database schema |
| `avenor add-repo <url>` | Track a GitHub URL or local git path |
| `avenor list-repos` | Show all tracked repositories with status |
| `avenor sync [--repo-id ID]` | Sync data inline (blocks until done) |
| `avenor sync --bg` | Queue sync via Celery (returns immediately) |
| `avenor serve [--host H] [--port P]` | Start the web dashboard |
| `avenor worker [-c N]` | Start a Celery background worker |
| `avenor quickstart <url>` | Init + add + sync in one command |

## Using the Web UI

### Adding a Repository
1. Paste a GitHub URL in the sidebar input (e.g., `https://github.com/owner/repo`)
2. Check "Auto-sync after adding" (enabled by default)
3. Click "Add & Track"
4. The repository syncs in the background — you'll see a toast notification when it's done
5. The page redirects to the repository's Overview page

### Navigating Pages
- **Overview**: Key stats, activity timeline, language breakdown, contributor types, recent releases
- **Contributions**: Commit activity, code churn, email domain breakdown, commit heatmap (hour x day)
- **Contributors**: Top contributors ranking, new contributor growth, bus factor, domain activity
- **Issues**: Open/closed stats, close rate, median close time, staleness analysis, top authors
- **Pull Requests**: Merge rate, merge time trends, PR size distribution (XS/S/M/L/XL), code impact
- **Codebase**: File hotspots, code churn over time, file type distribution, release cadence

### Time Period Controls
Every chart page has a time granularity selector: **Daily**, **Weekly**, or **Monthly**. This changes how data is bucketed in all time-series charts on that page.

### Syncing Data
- Click the **Sync** button in the top-right to refresh a repository's data
- If Celery is running, sync happens in the background with toast notifications
- If Celery is not running, sync runs inline (the page will take a moment to respond)

### Deleting a Repository
- Click the trash icon in the top-right when viewing a repository
- Confirm the deletion — this removes all collected data permanently

### Sidebar Search
- Type in the filter box at the top of the sidebar to quickly find repositories by name

## API Endpoints

### Repository Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/repos` | List all tracked repositories |
| `POST` | `/api/repos` | Add a repository (JSON: `{"url": "...", "auto_sync": true}`) |
| `DELETE` | `/api/repos/{id}` | Delete a repository and all its data |
| `GET` | `/api/repos/{id}/status` | Get sync status, errors, last synced time |
| `POST` | `/api/repos/{id}/sync` | Trigger a sync (background or inline) |

### Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/repos/{id}/overview` | Key stats (commits, PRs, issues, merge rate) |
| `GET` | `/api/repos/{id}/activity?period=month` | Activity time series |
| `GET` | `/api/repos/{id}/contributors?limit=15` | Top contributors |
| `GET` | `/api/repos/{id}/contributor-types` | Drive-by / repeat / core breakdown |
| `GET` | `/api/repos/{id}/bus-factor` | Bus factor calculation |
| `GET` | `/api/repos/{id}/issues/stats` | Issue close rate, median close time |
| `GET` | `/api/repos/{id}/prs/stats` | PR merge rate, median merge time |
| `GET` | `/api/repos/{id}/heatmap` | Commit activity heatmap (day x hour) |
| `GET` | `/api/repos/{id}/hotspots?limit=20` | Most frequently changed files |
| `GET` | `/api/compare?ids=1,2,3` | Multi-repo comparison |

## Architecture

```
┌──────────────────────────────────────────────┐
│                  Avenor                      │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ FastAPI  │  │  Celery  │  │Collectors │  │
│  │ Web UI + │◄─│  Worker  │─►│ GitHub    │  │
│  │ REST API │  │          │  │ Git log   │  │
│  └────┬─────┘  └────┬─────┘  └───────────┘  │
│       │              │                       │
│  ┌────▼──────────────▼────┐  ┌───────────┐  │
│  │   SQLAlchemy ORM       │  │   Redis   │  │
│  │  SQLite / PostgreSQL   │  │ Broker +  │  │
│  │                        │  │ Backend   │  │
│  └────────────────────────┘  └───────────┘  │
└──────────────────────────────────────────────┘
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AVENOR_DATA_DIR` | `./.avenor` | Data directory for SQLite DB and cloned repos |
| `AVENOR_DATABASE_URL` | `sqlite:///.avenor/avenor.db` | Database connection string |
| `AVENOR_GITHUB_TOKEN` | *(none)* | GitHub API token for higher rate limits |
| `AVENOR_REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery |
| `AVENOR_CELERY_BROKER` | same as `REDIS_URL` | Celery broker URL (override if different) |
| `AVENOR_CELERY_BACKEND` | same as `REDIS_URL` | Celery result backend URL |
| `AVENOR_HOST` | `127.0.0.1` | Web server bind address |
| `AVENOR_PORT` | `8000` | Web server port |
| `AVENOR_SECRET_KEY` | `development-only-secret-key` | Secret key (change in production) |

## Troubleshooting

### "GitHub API rate limit exceeded"

**Problem**: You see `GitHub API rate limit exceeded. Set AVENOR_GITHUB_TOKEN and retry.`

**Fix**: Create a GitHub personal access token and set it:
```bash
export AVENOR_GITHUB_TOKEN=ghp_your_token_here
```
Without a token, GitHub allows only 60 API requests per hour. With a token: 5,000/hour. For large repositories you need a token.

To create a token: GitHub Settings > Developer settings > Personal access tokens > Generate new token. No special scopes are needed for public repos.

### "Database is locked" (SQLite)

**Problem**: You see `database is locked` errors when running multiple processes.

**Fix**: SQLite doesn't support concurrent writes well. Solutions:
1. **Use PostgreSQL** for production: set `AVENOR_DATABASE_URL=postgresql+psycopg2://user:pass@host/db`
2. **Use Docker Compose** which uses PostgreSQL by default
3. **Don't run multiple sync processes** against the same SQLite file

### Sync takes a long time

**Problem**: `avenor sync` or `avenor quickstart` takes minutes to complete.

**Cause**: Large repositories have thousands of commits, issues, and PRs. Each PR requires an individual API call.

**Fixes**:
1. Set a GitHub token (increases rate limit from 60 to 5,000 requests/hour)
2. Use `avenor sync --bg` to run in background via Celery
3. From the web UI, just click Sync — it runs asynchronously when Celery is available

### Celery worker won't connect

**Problem**: `avenor worker` fails or sync tasks never run.

**Fix**: Make sure Redis is running:
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If not installed:
# Mac: brew install redis && brew services start redis
# Ubuntu: sudo apt install redis-server && sudo systemctl start redis
# Docker: docker run -d -p 6379:6379 redis:7-alpine
```

Then set the Redis URL if not using the default:
```bash
export AVENOR_REDIS_URL=redis://localhost:6379/0
```

**Note**: Celery is optional. Without it, sync runs inline (blocks the request but still works).

### Docker Compose won't start

**Problem**: `docker compose up` fails.

**Common fixes**:
1. Make sure Docker and Docker Compose are installed: `docker compose version`
2. Make sure ports 8000, 5432, 6379, 5555 are not in use
3. If the database container fails, clear volumes: `docker compose down -v && docker compose up -d`
4. Check logs: `docker compose logs app` or `docker compose logs worker`

### Charts are empty / no data showing

**Problem**: You see empty charts after adding a repository.

**Fix**: You need to sync the repository first:
1. From UI: Click the Sync button (top-right)
2. From CLI: `avenor sync --repo-id 1`
3. Wait for sync to complete (check status in sidebar or via `avenor list-repos`)

### "No module named 'avenor'" when running CLI

**Problem**: Running `avenor` command gives a module not found error.

**Fix**: Make sure you've installed the package and activated the virtual environment:
```bash
source .venv/bin/activate
pip install -e .
avenor --help
```

### Web server won't start / port already in use

**Problem**: `avenor serve` fails with "address already in use".

**Fix**: Use a different port:
```bash
avenor serve --port 8001
```

Or find and stop the process using port 8000:
```bash
lsof -ti:8000 | xargs kill
```

### Git clone fails during sync

**Problem**: Sync fails with git-related errors.

**Fix**: Make sure `git` is installed and accessible:
```bash
git --version
```

For private repositories, make sure your SSH keys or git credentials are configured.

## Running Tests

```bash
source .venv/bin/activate
pip install -e '.[dev]'
pytest tests/ -v
```
