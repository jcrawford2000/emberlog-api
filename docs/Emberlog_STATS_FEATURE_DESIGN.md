# Emberlog Stats Feature Design (v0.2)

Status: [Planned]  
Owner: Emberlog API  
Consumers: Emberlog Web (SSE + REST)  
Source: Trunk Recorder Status JSON (TR connects as WebSocket client; API is WebSocket server)

---

## 1. Overview

This feature adds a "Stats" subsystem to `emberlog-api` that:

1) Accepts a single inbound WebSocket connection from Trunk Recorder (TR) and ingests status messages.  
2) Normalizes TR messages into Emberlog-friendly schemas.  
3) Maintains short-lived, bounded in-memory history:
   - Decode rate time series (raw samples; rolling window up to 60 minutes).
   - Call feed rolling list (timestamp, talkgroup, description, duration) for last 5/15/60 minutes.
4) Exposes:
   - REST endpoints for initial load / window queries / downsampled series.
   - SSE endpoint for live updates to Emberlog Web.

This is internal-only for ingest (cluster trust). SSE to Web requires an API key.

---

## 2. Trunk Recorder Status Protocol Contract

### Reference

Protocol documentation:  
https://trunkrecorder.com/docs/notes/STATUS-JSON

### Supported Message Types (v0.2)

The following TR message types MUST be supported:

- `rates`
- `systems`
- `system`
- `calls_active`
- `call_start`
- `call_end`
- `recorders` (optional handling)
- `recorder` (optional handling)

### Parsing Rules

- Unknown message types MUST be ignored (log at debug level).
- Unknown fields MUST be ignored.
- Missing optional fields MUST NOT cause errors.
- JSON parsing errors MUST NOT crash the service.
- Implementation MUST be tolerant of future TR schema changes.

### Normalization Mapping (TR → Emberlog)

| TR Field         | Emberlog Field        |
|------------------|-----------------------|
| `sysNum`         | `system_id`           |
| `talkgroup`      | `talkgroup_id`        |
| `talkgrouptag`   | `talkgroup_label`     |
| `decoderate`     | `decode_rate`         |
| `id` (call)      | `call_id`             |

TR field names MUST NOT leak to Emberlog Web responses.

---

## 3. Goals

### Functional Goals

- Ingest TR `rates` messages (~3s cadence).
- Ingest call lifecycle messages (`call_start`, `call_end`, `calls_active`).
- Maintain rolling decode rate history (≤ 60 minutes).
- Maintain rolling call feed (≤ 60 minutes).
- Provide REST + SSE APIs for Emberlog Web.

### Non-Functional Goals

- Bounded memory usage.
- Single replica assumption for v0.2.
- Clean module boundaries for future refactor.

---

## 4. Assumptions and Constraints

### Deployment

- `emberlog-api` runs with replicas=1.
- Stats history is lost on pod restart (acceptable).

### Security

- TR ingest WebSocket is internal-only (cluster trust).
- REST + SSE endpoints require header-based API key:
  - Header: `X-API-Key: <key>`
  - Key sourced from environment variable.

### Scale (Current)

- 1 TR instance
- 4 systems
- <5 concurrent calls
- ~900 talkgroups

---

## 5. Architecture

### Module Structure (`app/stats/`)

- `models.py`
- `store.py`
- `ingest.py`
- `service.py`
- `sse.py`
- `routes.py`
- `auth.py`

### Data Flow

TR → WS ingest → Normalize → Store → SSE publish  
Web → REST (initial load) + SSE (live updates)

---

## 6. Normalized Data Models

### DecodeRateSample

```
{
  "ts": "ISO-8601 timestamp",
  "source_id": "string",
  "system_id": "string",
  "decode_rate": 87.2
}
```

### CallFeedItem

```
{
  "ts_end": "ISO-8601 timestamp",
  "ts_start": "ISO-8601 timestamp",
  "source_id": "string",
  "system_id": "string",
  "talkgroup_id": 2301,
  "talkgroup_label": "Fire Dispatch",
  "duration_sec": 14.0
}
```

### SourceStatus

```
{
  "source_id": "string",
  "connected": true,
  "last_seen": "ISO-8601 timestamp"
}
```

---

## 7. Memory Store Design

### Store Interface

- `update_system_info()`
- `append_decode_sample()`
- `track_call_start()`
- `track_call_end()`
- `get_decode_series(window, step)`
- `get_decode_summary(window)`
- `get_recent_calls(window, limit)`

### Retention Rules

- Decode samples: retain ≤ 60 minutes.
- Call feed: retain ≤ 60 minutes and enforce hard cap (e.g., 2000 items).

---

## 8. Downsampling

- Raw samples stored at ~3s cadence.
- REST supports optional `step` parameter.
- Downsampling computed on request.
- Summary stats computed on request.

---

## 9. API Contracts

### WebSocket Ingest

`WS /api/v1/stats/trunkrecorder/ws`

- Accept TR JSON messages.
- Internal-only access.

### SSE

`GET /api/v1/stats/stream`

Requires API key.

Events:

- `source_status`
- `decode_sample`
- `call_feed_item`

### REST Endpoints

- `GET /api/v1/stats/systems`
- `GET /api/v1/stats/decode?window=15m&step=10s`
- `GET /api/v1/stats/decode/summary?window=15m`
- `GET /api/v1/stats/calls/recent?window=15m&limit=200`

---

## 10. Incremental Story Plan

### Story 1
Create module skeleton + router wiring.

### Story 2
Add API key auth for stats REST + SSE.

### Story 3
Implement WebSocket ingest endpoint (log-only).

### Story 4
Implement system metadata + source status storage.

### Story 5
Implement decode sample storage + REST series endpoint.

### Story 6
Add downsampling + summary endpoint.

### Story 7
Implement call tracking + rolling call feed.

### Story 8
Implement SSE stream with decode + call events.

### Story 9
Hardening, schema cleanup, documentation updates.

---

## 11. Future Enhancements (Deferred)

- Redis-backed store
- Multi-replica support

---

## Implementation Status

- Story 1 delivered (module skeleton + route wiring).
- Placeholder endpoint available:
  - `GET /api/v1/stats/systems`
  - Returns `200` with a scaffold payload:
    - `source_status: null`
    - `systems: []`
    - `latest_decode: {}`
- Alerting/thresholds
- Recorder health dashboards
