import httpx
import pytest

from emberlog_api.app.stats.store import reset_source_status


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=True
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_stats_source_status():
    reset_source_status()
    yield
    reset_source_status()
