import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/testdb")

from emberlog_api.utils import loggersetup

loggersetup.LOGGING["handlers"].pop("file_app", None)
loggersetup.LOGGING["loggers"][""]["handlers"] = ["console"]

from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.main import get_healthz, get_readyz


class FakeCursor:
    def __init__(self, should_fail: bool):
        self.should_fail = should_fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, _query: str):
        if self.should_fail:
            raise RuntimeError("db unavailable")


class FakeConnection:
    def __init__(self, should_fail: bool):
        self.should_fail = should_fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(should_fail=self.should_fail)


class FakePool:
    def __init__(self, should_fail: bool):
        self.should_fail = should_fail

    def connection(self) -> FakeConnection:
        return FakeConnection(should_fail=self.should_fail)


health_app = FastAPI()
health_app.get("/healthz")(get_healthz)
health_app.get("/readyz")(get_readyz)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    transport = httpx.ASGITransport(app=health_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=True
    ) as client:
        yield client


@pytest.mark.anyio
async def test_healthz_returns_ok(async_client):
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readyz_returns_ok_when_db_is_available(async_client):
    async def override_pool():
        return FakePool(should_fail=False)

    health_app.dependency_overrides[get_pool] = override_pool
    try:
        response = await async_client.get("/readyz")
    finally:
        health_app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readyz_returns_503_when_db_is_unavailable(async_client):
    async def override_pool():
        return FakePool(should_fail=True)

    health_app.dependency_overrides[get_pool] = override_pool
    try:
        response = await async_client.get("/readyz")
    finally:
        health_app.dependency_overrides = {}

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "db_unavailable"}
