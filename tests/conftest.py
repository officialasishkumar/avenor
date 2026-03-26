from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch) -> Generator[None, None, None]:
    monkeypatch.setenv("AVENOR_DATA_DIR", str(tmp_path / ".avenor"))
    monkeypatch.delenv("AVENOR_DATABASE_URL", raising=False)

    from avenor.config import get_settings
    from avenor.db import reset_db_state

    get_settings.cache_clear()
    reset_db_state()
    yield
    get_settings.cache_clear()
    reset_db_state()
