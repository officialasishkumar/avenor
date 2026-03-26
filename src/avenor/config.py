from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    project_root: Path
    data_dir: Path
    repos_dir: Path
    database_url: str
    host: str
    port: int
    github_token: str | None
    secret_key: str

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)


AppConfig = Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    default_data_dir = project_root / ".avenor"
    data_dir = Path(os.getenv("AVENOR_DATA_DIR", default_data_dir))
    repos_dir = data_dir / "repos"
    default_database = data_dir / "avenor.db"

    settings = Settings(
        app_name="Avenor",
        project_root=project_root,
        data_dir=data_dir,
        repos_dir=repos_dir,
        database_url=os.getenv("AVENOR_DATABASE_URL", f"sqlite:///{default_database}"),
        host=os.getenv("AVENOR_HOST", "127.0.0.1"),
        port=int(os.getenv("AVENOR_PORT", "8000")),
        github_token=os.getenv("AVENOR_GITHUB_TOKEN"),
        secret_key=os.getenv("AVENOR_SECRET_KEY", "development-only-secret-key"),
    )
    settings.ensure_directories()
    return settings


def get_config() -> Settings:
    return get_settings()
