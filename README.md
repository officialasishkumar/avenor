# Avenor

**Unified open-source analytics platform** — collection, storage, and visualization in one project.

## Features

- **Data Collection**: GitHub API + git log parsing with background task queue (Celery + Redis)
- **20+ Health Metrics**: Bus factor, contributor types, PR merge times, issue staleness, code churn, domain affiliation, and more
- **6-Page Analytics Dashboard**: Overview, Contributions, Contributors, Issues, Pull Requests, Codebase
- **Interactive Plotly Charts**: Heatmaps, area charts, donut charts, horizontal bars, multi-line time series
- **Full REST API**: JSON endpoints for all metrics at `/api/repos/{id}/*`
- **Multi-Repo Comparison**: Side-by-side repository metrics on the home dashboard
- **Docker Compose**: One-command deployment with app, Celery worker, Redis, PostgreSQL, and Flower monitoring
- **CLI**: `avenor quickstart <url>` to go from zero to dashboard in one command
- **Async UI**: Toast notifications, background sync, sidebar search, mobile navigation
- **Time Period Controls**: Switch between daily, weekly, and monthly chart granularity
- **Settings Page**: Configure GitHub token and view system info directly from the UI
- **Sync All**: One-click to sync every tracked repository at once
- **Shorthand Input**: Type `owner/repo` instead of full URLs when adding repositories

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

You can configure this in two ways:

**Option A — From the UI (recommended):**
Open http://127.0.0.1:8000/settings and paste your token. It's saved locally in `.avenor/settings.json`.

**Option B — Via environment variable:**
```bash
export AVENOR_GITHUB_TOKEN=ghp_your_token_here
```

Without a token you're limited to 60 GitHub API requests/hour. With a token: 5,000/hour. The sidebar shows a warning if no token is configured.

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
1. Use the form on the home page or in the sidebar
2. Type a shorthand like `owner/repo` or a full URL like `https://github.com/owner/repo`
3. Auto-sync is enabled by default — the repository syncs in the background
4. You'll see toast notifications for progress and completion
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
- Click **Sync All** on the home page to sync every tracked repository at once
- If Celery is running, sync happens in the background with toast notifications
- If Celery is not running, sync runs inline (the page will take a moment to respond)

### Settings
- Open the **Settings** page (gear icon in the sidebar) to configure your GitHub token
- The settings page also shows system information (data directory, database, Redis URL)

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
| `POST` | `/api/repos/sync-all` | Sync all tracked repositories at once |
| `GET` | `/api/settings` | Get current settings (token status, data dir) |
| `POST` | `/api/settings` | Save settings (JSON: `{"github_token": "..."}`) |

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

**Fix**: Configure a GitHub personal access token using one of these methods:
1. **From the UI**: Go to http://localhost:8000/settings and paste your token
2. **From the CLI**: `export AVENOR_GITHUB_TOKEN=ghp_your_token_here`

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

## Hosting & Deployment Guide

### Option 1: Docker Compose (recommended for production)

The simplest way to deploy Avenor with all services:

```bash
# Clone the repository
git clone https://github.com/officialasishkumar/avenor.git
cd avenor

# Set your GitHub token (optional but recommended)
export AVENOR_GITHUB_TOKEN=ghp_your_token_here

# Start all services
docker compose up -d
```

This starts 5 services:

| Service | Port | Description |
|---------|------|-------------|
| **app** | 8000 | Web dashboard + REST API |
| **worker** | — | Celery background worker for async sync |
| **postgres** | 5432 | PostgreSQL database |
| **redis** | 6379 | Message broker for Celery |
| **flower** | 5555 | Celery task monitoring UI |

**Updating:**
```bash
git pull
docker compose build
docker compose up -d
```

**Persistent data:** Docker volumes (`pg-data`, `app-data`, `app-repos`, `redis-data`) survive container restarts. To reset everything: `docker compose down -v`.

### Option 2: Single server with systemd

For a bare-metal or VM deployment without Docker:

```bash
# 1. Install system dependencies
sudo apt update && sudo apt install -y python3.12 python3.12-venv git redis-server postgresql

# 2. Create a dedicated user
sudo useradd -m -s /bin/bash avenor
sudo su - avenor

# 3. Clone and install
git clone https://github.com/officialasishkumar/avenor.git
cd avenor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 4. Set up PostgreSQL
sudo -u postgres createuser avenor
sudo -u postgres createdb -O avenor avenor

# 5. Configure environment
cat > ~/.avenor.env << 'EOF'
AVENOR_DATABASE_URL=postgresql+psycopg2://avenor@localhost/avenor
AVENOR_REDIS_URL=redis://localhost:6379/0
AVENOR_HOST=0.0.0.0
AVENOR_PORT=8000
AVENOR_DATA_DIR=/home/avenor/avenor/.avenor
AVENOR_SECRET_KEY=change-this-to-a-random-string
# AVENOR_GITHUB_TOKEN=ghp_your_token_here
EOF

# 6. Initialize database
source ~/.avenor.env
avenor init-db
```

Create systemd service files:

**/etc/systemd/system/avenor-web.service:**
```ini
[Unit]
Description=Avenor Web Dashboard
After=network.target postgresql.service redis.service

[Service]
User=avenor
WorkingDirectory=/home/avenor/avenor
EnvironmentFile=/home/avenor/.avenor.env
ExecStart=/home/avenor/avenor/.venv/bin/avenor serve --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**/etc/systemd/system/avenor-worker.service:**
```ini
[Unit]
Description=Avenor Celery Worker
After=network.target postgresql.service redis.service

[Service]
User=avenor
WorkingDirectory=/home/avenor/avenor
EnvironmentFile=/home/avenor/.avenor.env
ExecStart=/home/avenor/avenor/.venv/bin/celery -A avenor.tasks worker -l info -Q default,collection -c 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now avenor-web avenor-worker
```

### Option 3: Deploy behind a reverse proxy (Nginx)

For production, put Avenor behind Nginx with HTTPS:

```nginx
server {
    listen 80;
    server_name analytics.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name analytics.example.com;

    ssl_certificate     /etc/letsencrypt/live/analytics.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/analytics.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Optional: expose Flower task monitor on a subpath
    location /flower/ {
        proxy_pass http://127.0.0.1:5555/;
        proxy_set_header Host $host;
    }
}
```

```bash
# Get a free SSL certificate
sudo certbot --nginx -d analytics.example.com
```

### Option 4: Lightweight (SQLite, no Redis)

For personal use or small teams where you don't need background sync:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
avenor init-db
avenor serve --host 0.0.0.0 --port 8000
```

This runs with SQLite and no Celery. Sync happens inline when you click the Sync button (the request blocks until done). Good for tracking a handful of repositories.

### Production checklist

- [ ] Set `AVENOR_SECRET_KEY` to a random string (not the default)
- [ ] Configure a GitHub token (via UI Settings page or `AVENOR_GITHUB_TOKEN`)
- [ ] Use PostgreSQL instead of SQLite for concurrent access
- [ ] Set up Redis + Celery worker for background sync
- [ ] Put behind a reverse proxy (Nginx/Caddy) with HTTPS
- [ ] Set `AVENOR_HOST=0.0.0.0` to listen on all interfaces
- [ ] Back up your PostgreSQL database regularly
- [ ] Monitor with Flower (port 5555) if using Celery

## Running Tests

```bash
source .venv/bin/activate
pip install -e '.[dev]'
pytest tests/ -v
```

## License

MIT License. See [LICENSE](LICENSE) for details.
