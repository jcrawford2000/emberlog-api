from datetime import datetime, timezone

import pytest

from emberlog_api.app.services import mqtt_consumer


@pytest.mark.anyio
async def test_handle_rates_message_calls_repo_upsert(monkeypatch):
    calls: list[dict] = []

    async def fake_upsert_decode_rate(pool, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        mqtt_consumer.traffic_repo, "upsert_decode_rate", fake_upsert_decode_rate
    )

    payload = {
        "type": "rates",
        "rates": [
            {
                "sys_num": 1,
                "sys_name": "PRWC-J",
                "decoderate": 0.41,
                "decoderate_interval": 3.0,
                "control_channel": 769118750.0,
            }
        ],
        "timestamp": 1771215501,
        "instance_id": "trunk-recorder",
    }

    await mqtt_consumer.handle_rates_message(pool=None, payload=payload)

    assert len(calls) == 1
    assert calls[0]["instance_id"] == "trunk-recorder"
    assert calls[0]["sys_num"] == 1
    assert calls[0]["sys_name"] == "PRWC-J"
    assert calls[0]["decoderate_raw"] == 0.41
    assert calls[0]["decoderate_pct"] == 41.0
    assert calls[0]["decoderate_interval_s"] == 3.0
    assert calls[0]["control_channel_hz"] == 769118750
    assert calls[0]["updated_at"] == datetime.fromtimestamp(1771215501, tz=timezone.utc)
