import pytest

from emberlog_api.app.main import app as emberlog_app


@pytest.fixture
def app():
    return emberlog_app


@pytest.mark.anyio
async def test_stats_systems_placeholder(async_client):
    response = await async_client.get("/api/v1/stats/systems")
    assert response.status_code == 200
    assert response.json() == {
        "source_status": None,
        "systems": [],
        "latest_decode": {},
    }
