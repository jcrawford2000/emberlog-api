from __future__ import annotations

import logging
from typing import Any, Dict
from emberlog_api.app.core.settings import settings

import httpx

log = logging.getLogger("emberlog_api.notifier.client")


class NotifierClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=settings.notifier_base_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def on_new_incident(self, event_type: str, payload: Dict[str, Any]):
        log.debug("Notifier Calls for new incident (Type:%s)", event_type)
        try:
            log.debug("Posting to Notifier Service")
            r = await self._client.post("/api/v1/events/new_incident", json=payload)
            r.raise_for_status()
            log.debug("Status: %s", r.status_code)
        except httpx.HTTPStatusError as e:
            detail = e.response.text
            log.error("API Error %s:%s", e.response.status_code, detail)
            raise
        data = r.json()
        log.debug("Result: %s", data)

