from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger("emberlog_api.db.drain.OutboxDrain")

# ------------- Delivery Interface -------------------------------------------


class DeliveryError(Exception):
    """Raised by delivery handlers on non-transient errors (still retried up to max)."""


class DeliveryHandler(Protocol):
    async def __call__(self, event_type: str, payload: Dict[str, Any], /) -> None: ...


# Example multiplexer for event types -> concrete channels
class Router:
    def __init__(self, routes: Dict[str, DeliveryHandler]):
        self.routes = routes

    async def deliver(self, event_type: str, payload: Dict[str, Any]) -> None:
        handler = self.routes.get(event_type)
        if not handler:
            raise DeliveryError(f"No handler for event_type={event_type}")
        await handler(event_type, payload)


# ------------- Concrete Handlers (stubs you can wire up) --------------------


async def handle_incident_created(event_type: str, payload: Dict[str, Any]) -> None:
    """
    Idempotent ‘incident.created’ example.
    For v1, you might:
      - Fan out to in-memory SSE clients (Emberlog Web)
      - Push to a Webhook subscriber registry (future)
      - Enqueue SMS/email (future)
    Make side-effects idempotent (e.g., upsert on subscriber delivery table)
    """
    # Demo: log-only
    incident_id = payload.get("incident_id") or payload.get("id")
    log.info(
        "Deliver incident.created incident_id=%s addr=%s",
        incident_id,
        payload.get("address"),
    )


@dataclass
class OutboxDrainConfig:
    pool: AsyncConnectionPool
    poll_sleep_s: float = 1.0
    max_retries: int = 5
    base_backoff_s: float = 3.0
    backoff_factor: float = 2.0
    max_concurrency: int = 5
    batch_size: int = 5
    jitter_s: float = 0.5


class OutboxDrain:

    def __init__(self, cfg: OutboxDrainConfig, router: Router):
        self.cfg = cfg
        self._stop = asyncio.Event()
        self._pool = cfg.pool
        self._log = logging.getLogger("emberlog_api.notifier.drain.OutboxDrain")
        self._sem = asyncio.Semaphore(self.cfg.max_concurrency)
        self._task: Optional[asyncio.Task] = None
        self.router = router

    async def start(self) -> None:
        self._log.info(
            "Outbox drain starting (batch=%d, conc=%d)",
            self.cfg.batch_size,
            self.cfg.max_concurrency,
        )
        self._task = asyncio.create_task(self._main_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._log.info("Outbox drain stopped")

    async def _main_loop(self) -> None:
        try:
            while not self._stop.is_set():
                rows = await self._claim_rows(limit=self.cfg.batch_size)
                if not rows:
                    await asyncio.sleep(self.cfg.poll_sleep_s)
                    continue
                tasks = [asyncio.create_task(self._process_row(row)) for row in rows]
                await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self._log.info("Outbound Drain Loop Cancelled")
        except Exception:
            self._log.exception("Drain Loop Crashed")
            raise

    async def _claim_rows(self, limit: int):
        sql = """
            WITH cte AS (
                SELECT id
                FROM incident_outbox
                WHERE status = 'pending'
                    AND available_at <= now()
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE incident_outbox o
            SET status = 'processing'
            FROM cte
            WHERE o.id = cte.id
            RETURNING o.id, o.event_type, o.payload, o.attempts;
        """
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, (limit,))
                return await cur.fetchall()

    async def _process_row(self, row: Dict[str, Any]) -> None:
        async with self._sem:
            oid = row["id"]
            event_type = row["event_type"]
            payload = row["payload"]
            retry_count = row["attempts"]
            try:
                await self.router.deliver(event_type, payload)
            except Exception as e:
                await self._on_failure(oid, retry_count, e)
                return
            await self._on_success(oid)

    async def _on_success(self, oid: int) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM incident_outbox WHERE id = %s;", (oid,))
        self._log.debug("outbox %s delivered -> deleted", oid)

    async def _on_failure(self, oid: int, retry_count: int, err: Exception) -> None:
        next_retry = retry_count + 1
        # dead-letter
        if next_retry > self.cfg.max_retries:
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE incident_outbox SET status='dead', last_error=%s WHERE id=%s;",
                        (str(err)[:500], oid),
                    )
            self._log.error(
                "outbox %s DEAD after %d retries: %s", oid, retry_count, err
            )
            return

        delay = self._compute_backoff(next_retry)
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE incident_outbox
                       SET status='pending',
                           attempts = attempts + 1,
                           available_at = now() + make_interval(secs => %s),
                           last_error = %s
                     WHERE id = %s;
                    """,
                    (delay, str(err)[:500], oid),
                )
        self._log.warning(
            "outbox %s retry=%d in %.2fs err=%s", oid, next_retry, delay, err
        )

    def _compute_backoff(self, attempt: int) -> float:
        base = self.cfg.base_backoff_s * (self.cfg.backoff_factor ** (attempt - 1))
        jitter = random.uniform(-self.cfg.jitter_s, self.cfg.jitter_s)
        return max(1.0, base + jitter)
