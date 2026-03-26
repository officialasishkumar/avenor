# Avenor

Avenor is a single-project rewrite target for the Augur + 8Knot split stack.

Goals:

- one repository
- one local database
- one web process
- one CLI
- no Redis, RabbitMQ, Postgres sidecars required for local use
- git-native collection with optional GitHub enrichment
- local git repository support
- a familiar multi-page analytics UI

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/avenor init-db
.venv/bin/avenor add-repo ../8knot-source
.venv/bin/avenor sync --repo-id 1
.venv/bin/avenor serve
```

`add-repo` accepts either a GitHub repository URL or a local git repository path.

If you already have `uv` installed, the same workflow can be run with `uv run ...`.

## Core Commands

```bash
.venv/bin/avenor init-db
.venv/bin/avenor add-repo ../8knot-source
.venv/bin/avenor add-repo https://github.com/chaoss/augur.git
.venv/bin/avenor sync --repo-id 1
.venv/bin/avenor serve
.venv/bin/pytest
```

## Environment

- `AVENOR_DATA_DIR`: runtime directory. Defaults to `./.avenor`
- `AVENOR_DATABASE_URL`: override the SQLite database URL
- `AVENOR_GITHUB_TOKEN`: optional GitHub token for issues, PRs, releases, and repo metadata
