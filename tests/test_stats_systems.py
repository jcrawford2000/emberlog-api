import pytest
from fastapi import FastAPI

from emberlog_api.app.core.settings import settings
from emberlog_api.app.stats import routes as stats_routes


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(stats_routes.router, prefix="/api/v1")
    return test_app


@pytest.mark.anyio
async def test_stats_systems_requires_api_key_when_configured(async_client, monkeypatch):
    monkeypatch.setattr(settings, "emberlog_api_key", "devkey")
    monkeypatch.setattr(settings, "emberlog_env", "prod")

    response = await async_client.get("/api/v1/stats/systems")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.anyio
async def test_stats_systems_rejects_wrong_api_key(async_client, monkeypatch):
    monkeypatch.setattr(settings, "emberlog_api_key", "devkey")
    monkeypatch.setattr(settings, "emberlog_env", "prod")

    response = await async_client.get(
        "/api/v1/stats/systems", headers={"X-API-Key": "wrong"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.anyio
async def test_stats_systems_accepts_correct_api_key(async_client, monkeypatch):
    monkeypatch.setattr(settings, "emberlog_api_key", "devkey")
    monkeypatch.setattr(settings, "emberlog_env", "prod")

    response = await async_client.get(
        "/api/v1/stats/systems", headers={"X-API-Key": "devkey"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "source_status": None,
        "systems": [],
        "latest_decode": {},
    }


@pytest.mark.anyio
async def test_stats_systems_allows_unauthenticated_in_dev_without_key(
    async_client, monkeypatch
):
    monkeypatch.setattr(settings, "emberlog_api_key", "")
    monkeypatch.setattr(settings, "emberlog_env", "dev")

    response = await async_client.get("/api/v1/stats/systems")
    assert response.status_code == 200
    assert response.json() == {
        "source_status": None,
        "systems": [],
        "latest_decode": {},
    }


@pytest.mark.anyio
async def test_stats_systems_rejects_when_key_missing_in_prod(async_client, monkeypatch):
    monkeypatch.setattr(settings, "emberlog_api_key", "")
    monkeypatch.setattr(settings, "emberlog_env", "prod")

    response = await async_client.get("/api/v1/stats/systems")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
