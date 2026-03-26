from __future__ import annotations

from fastapi.testclient import TestClient

from avenor.web.app import create_app


def test_healthz_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_page_loads() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "Avenor" in response.text


def test_add_repository_redirects_to_overview() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/repos",
        data={"repo_url": "https://github.com/chaoss/augur"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/overview" in response.headers["location"]
