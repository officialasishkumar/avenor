# Avenor

Avenor is a single-project rewrite target for the Augur + 8Knot split stack.

Goals:

- one repository
- one local database
- one web process
- one CLI
- no Redis, RabbitMQ, Postgres sidecars required for local use
- git-native collection with optional GitHub enrichment
- a familiar multi-page analytics UI

## Quick Start

```bash
uv run avenor demo
uv run avenor serve --port 8051
```

The `demo` command imports and syncs local git repositories from the current
workspace when available. The UI then runs at `http://127.0.0.1:8051`.

## Core Commands

```bash
uv run avenor init-db
uv run avenor add-project ../augur --group Workspace
uv run avenor add-project https://github.com/chaoss/augur.git --group Workspace
uv run avenor sync --all
uv run avenor serve
uv run pytest
```

## Environment

- `AVENOR_DATA_DIR`: runtime directory. Defaults to `./.avenor`
- `AVENOR_DB_URL`: override the SQLite database URL
- `AVENOR_GITHUB_TOKEN`: optional GitHub token for issues, PRs, releases, and repo metadata

