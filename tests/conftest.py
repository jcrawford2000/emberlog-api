import httpx
import pytest


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
