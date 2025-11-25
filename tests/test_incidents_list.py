import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/testdb")

from emberlog_api.utils import loggersetup

loggersetup.LOGGING["handlers"].pop("file_app", None)
loggersetup.LOGGING["loggers"][""]["handlers"] = ["console"]

from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.db.repositories import incidents as incidents_repo
from emberlog_api.app.main import app
from emberlog_api.models.incident import IncidentOut


client = TestClient(app)


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
    app.dependency_overrides[get_pool] = lambda: None
    monkeypatch.setattr(incidents_repo, "list_incidents", fake_list_incidents)
    yield
    app.dependency_overrides = {}


def test_list_incidents_default_pagination():
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["total"] == 3
    assert [item["id"] for item in payload["items"]] == [3, 2, 1]


def test_filter_by_incident_type():
    response = client.get("/api/v1/incidents", params={"incident_type": "medical"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 2


def test_filter_by_channel():
    response = client.get("/api/v1/incidents", params={"channel": "A1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["id"] for item in payload["items"]] == [3, 1]


def test_filter_by_date_range():
    start = datetime(2024, 5, 2, tzinfo=timezone.utc)
    end = start + timedelta(days=1, hours=12)
    response = client.get(
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


def test_filter_by_units():
    response = client.get(
        "/api/v1/incidents",
        params=[("units", "E1"), ("units", "X9")],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 1


def test_filter_by_address_search():
    response = client.get("/api/v1/incidents", params={"address_search": "Pine"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 2


def test_pagination_parameters():
    response = client.get("/api/v1/incidents", params={"page": 2, "page_size": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["total"] == 3
    assert [item["id"] for item in payload["items"]] == [2]
