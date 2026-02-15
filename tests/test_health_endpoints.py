import pytest

from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.main import app as emberlog_app


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


@pytest.fixture
def app():
    return emberlog_app


@pytest.mark.anyio
async def test_healthz_returns_ok(async_client):
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("X-Request-ID")


@pytest.mark.anyio
async def test_healthz_propagates_request_id(async_client):
    response = await async_client.get("/healthz", headers={"X-Request-ID": "req-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-123"


@pytest.mark.anyio
async def test_readyz_returns_ok_when_db_is_available(async_client):
    async def override_pool():
        return FakePool(should_fail=False)

    emberlog_app.dependency_overrides[get_pool] = override_pool
    try:
        response = await async_client.get("/readyz")
    finally:
        emberlog_app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readyz_returns_503_when_db_is_unavailable(async_client):
    async def override_pool():
        return FakePool(should_fail=True)

    emberlog_app.dependency_overrides[get_pool] = override_pool
    try:
        response = await async_client.get("/readyz")
    finally:
        emberlog_app.dependency_overrides = {}

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "db_unavailable"}
