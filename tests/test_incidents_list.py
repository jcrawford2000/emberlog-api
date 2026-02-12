from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI

from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.db.repositories import incidents as incidents_repo
from emberlog_api.app.api.v1.routers import incidents
from emberlog_api.models.incident import IncidentOut


incidents_app = FastAPI()
incidents_app.include_router(incidents.router, prefix="/api/v1")


SAMPLE_INCIDENTS = [
    IncidentOut(
        id=1,
        dispatched_at=datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc),
        special_call=False,
        units=["E1", "M2"],
        channel="A1",
        incident_type="fire",
        address="123 Main Street",
        source_audio="audio1",
        original_text="Incident one",
        transcript=None,
        parsed={"note": "first"},
        created_at=datetime(2024, 5, 1, 12, 5, tzinfo=timezone.utc),
    ),
    IncidentOut(
        id=2,
        dispatched_at=datetime(2024, 5, 2, 12, 0, tzinfo=timezone.utc),
        special_call=True,
        units=["M3"],
        channel="A2",
        incident_type="medical",
        address="456 Pine Avenue",
        source_audio="audio2",
        original_text="Incident two",
        transcript=None,
        parsed={"note": "second"},
        created_at=datetime(2024, 5, 2, 12, 5, tzinfo=timezone.utc),
    ),
    IncidentOut(
        id=3,
        dispatched_at=datetime(2024, 5, 3, 12, 0, tzinfo=timezone.utc),
        special_call=False,
        units=["E5"],
        channel="A1",
        incident_type="fire",
        address="789 Oak Road",
        source_audio="audio3",
        original_text="Incident three",
        transcript=None,
        parsed={"note": "third"},
        created_at=datetime(2024, 5, 3, 12, 5, tzinfo=timezone.utc),
    ),
]


async def fake_list_incidents(
    pool,
    *,
    from_dispatched_at=None,
    to_dispatched_at=None,
    incident_type=None,
    channel=None,
    units=None,
    address_search=None,
    limit=50,
    offset=0,
):
    filtered = list(SAMPLE_INCIDENTS)

    if from_dispatched_at:
        filtered = [
            inc for inc in filtered if inc.dispatched_at >= from_dispatched_at
        ]

    if to_dispatched_at:
        filtered = [inc for inc in filtered if inc.dispatched_at <= to_dispatched_at]

    if incident_type:
        filtered = [inc for inc in filtered if inc.incident_type == incident_type]

    if channel:
        filtered = [inc for inc in filtered if inc.channel == channel]

    if units:
        filtered = [
            inc
            for inc in filtered
            if inc.units and set(inc.units).intersection(units)
        ]

    if address_search:
        lowered = address_search.lower()
        filtered = [
            inc
            for inc in filtered
            if inc.address and lowered in inc.address.lower()
        ]

    filtered.sort(key=lambda inc: inc.dispatched_at, reverse=True)
    total = len(filtered)
    items = filtered[offset : offset + limit]

    return items, total


@pytest.fixture(autouse=True)
def override_dependencies(monkeypatch):
    async def override_pool():
        return None

    incidents_app.dependency_overrides[get_pool] = override_pool
    monkeypatch.setattr(incidents_repo, "list_incidents", fake_list_incidents)
    yield
    incidents_app.dependency_overrides = {}


@pytest.fixture
def app():
    return incidents_app


@pytest.mark.anyio
async def test_list_incidents_default_pagination(async_client):
    response = await async_client.get("/api/v1/incidents")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["total"] == 3
    assert [item["id"] for item in payload["items"]] == [3, 2, 1]


@pytest.mark.anyio
async def test_filter_by_incident_type(async_client):
    response = await async_client.get(
        "/api/v1/incidents", params={"incident_type": "medical"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 2


@pytest.mark.anyio
async def test_filter_by_channel(async_client):
    response = await async_client.get("/api/v1/incidents", params={"channel": "A1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["id"] for item in payload["items"]] == [3, 1]


@pytest.mark.anyio
async def test_filter_by_date_range(async_client):
    start = datetime(2024, 5, 2, tzinfo=timezone.utc)
    end = start + timedelta(days=1, hours=12)
    response = await async_client.get(
        "/api/v1/incidents",
        params={
            "from_dispatched_at": start.isoformat(),
            "to_dispatched_at": end.isoformat(),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["id"] for item in payload["items"]] == [3, 2]


@pytest.mark.anyio
async def test_filter_by_units(async_client):
    response = await async_client.get(
        "/api/v1/incidents",
        params=[("units", "E1"), ("units", "X9")],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 1


@pytest.mark.anyio
async def test_filter_by_address_search(async_client):
    response = await async_client.get(
        "/api/v1/incidents", params={"address_search": "Pine"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 2


@pytest.mark.anyio
async def test_pagination_parameters(async_client):
    response = await async_client.get(
        "/api/v1/incidents", params={"page": 2, "page_size": 1}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["total"] == 3
    assert [item["id"] for item in payload["items"]] == [2]
