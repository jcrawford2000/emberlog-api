import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.websockets import WebSocketDisconnect

from emberlog_api.app.core.settings import settings
from emberlog_api.app.stats import routes as stats_routes


_DISCONNECT = object()


class ControlledWebSocket:
    """Minimal websocket test double for driving the stats ingest route."""

    def __init__(self) -> None:
        self.accepted = False
        self._queue: asyncio.Queue[object] = asyncio.Queue()
        self.client = SimpleNamespace(host="127.0.0.1")
        self.url = SimpleNamespace(path="/api/v1/stats/trunkrecorder/ws")
        self.headers = {"x-api-key": "test", "authorization": "Bearer secret"}

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        item = await self._queue.get()
        if item is _DISCONNECT:
            raise WebSocketDisconnect()
        return str(item)

    async def push_text(self, text: str) -> None:
        await self._queue.put(text)

    async def disconnect(self) -> None:
        await self._queue.put(_DISCONNECT)


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(stats_routes.router, prefix="/api/v1")
    return test_app


@pytest.mark.anyio
async def test_stats_ws_ingest_updates_source_status_lifecycle(async_client, monkeypatch):
    monkeypatch.setattr(settings, "emberlog_api_key", "devkey")
    monkeypatch.setattr(settings, "emberlog_env", "prod")

    before = await async_client.get("/api/v1/stats/systems", headers={"X-API-Key": "devkey"})
    assert before.status_code == 200
    assert before.json()["source_status"] is None

    websocket = ControlledWebSocket()
    ws_task = asyncio.create_task(stats_routes.stats_trunkrecorder_ws(websocket=websocket))

    while not websocket.accepted:
        await asyncio.sleep(0)

    await websocket.push_text('{"type":"rates"}')
    await websocket.push_text('{"type":"unknown_future_type","instanceKey":"abc"}')
    await asyncio.sleep(0)

    during = await async_client.get("/api/v1/stats/systems", headers={"X-API-Key": "devkey"})
    assert during.status_code == 200
    during_status = during.json()["source_status"]
    assert during_status["source_id"] == "trunkrecorder-default"
    assert during_status["connected"] is True
    assert during_status["last_seen"]

    await websocket.disconnect()
    await ws_task

    after = await async_client.get("/api/v1/stats/systems", headers={"X-API-Key": "devkey"})
    assert after.status_code == 200
    after_status = after.json()["source_status"]
    assert after_status["source_id"] == "trunkrecorder-default"
    assert after_status["connected"] is False
    assert after_status["last_seen"]


@pytest.mark.anyio
async def test_stats_ws_ingest_ignores_invalid_json_and_stays_open(async_client, monkeypatch):
    monkeypatch.setattr(settings, "emberlog_api_key", "devkey")
    monkeypatch.setattr(settings, "emberlog_env", "prod")

    websocket = ControlledWebSocket()
    ws_task = asyncio.create_task(stats_routes.stats_trunkrecorder_ws(websocket=websocket))

    while not websocket.accepted:
        await asyncio.sleep(0)

    await websocket.push_text("not-json")
    await websocket.push_text('{"type":"rates","instanceId":"tr-a"}')
    await asyncio.sleep(0)

    during = await async_client.get("/api/v1/stats/systems", headers={"X-API-Key": "devkey"})
    assert during.status_code == 200
    during_status = during.json()["source_status"]
    assert during_status["source_id"] == "tr-a"
    assert during_status["connected"] is True
    assert during_status["last_seen"]

    await websocket.disconnect()
    await ws_task
