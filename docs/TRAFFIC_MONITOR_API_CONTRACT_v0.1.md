# Emberlog Traffic Monitor API Contract v0.1

Date: 2026-02-16  
Scope: **MVP Traffic Monitor** (Monitor → Traffic Monitor) backed by Trunk Recorder MQTT.

This contract defines **what Emberlog Web calls** and **what Emberlog API must provide** for the Traffic Monitor page.

## Goals

- Show **System+Site decode rates** (from MQTT `rates`)
- Show **Recorder summary** (from MQTT `recorders`)
- Show **Live calls** (from MQTT `calls_active`)
- Simple, reliable **polling** (no SSE/WebSockets for MVP)
- Persist only **latest snapshots** in Postgres (no history tables for MVP)

## Non-Goals

- Dispatch transcripts on this page (separate page)
- Controlling Trunk Recorder (start/stop/config)
- Redis or other caching layer
- Historical charts / time-series retention (future)

## MQTT Inputs

Topic prefix (configurable): `emberlog/trunkrecorder`

Minimum subscriptions for MVP:

- `{prefix}/rates`
- `{prefix}/recorders`
- `{prefix}/calls_active`

### Rates example (input)

```json
{
  "type": "rates",
  "rates": [
    {
      "sys_num": 1,
      "sys_name": "PRWC-J",
      "decoderate": 41.0,
      "decoderate_interval": 3.0,
      "control_channel": 769118750.0
    }
  ],
  "timestamp": 1771215501,
  "instance_id": "trunk-recorder"
}
```

### Recorders example (input)

```json
{
  "type": "recorders",
  "recorders": [
    {
      "id": "0_1",
      "src_num": 0,
      "rec_num": 1,
      "type": "P25",
      "freq": 769618750.0,
      "rec_state": 4,
      "rec_state_type": "IDLE"
    }
  ],
  "timestamp": 1771215726,
  "instance_id": "trunk-recorder"
}
```

### Calls Active example (input)

```json
{
  "type": "calls_active",
  "calls": [
    {
      "id": "1_4499_1771215827",
      "sys_num": 1,
      "sys_name": "PRWC-J",
      "freq": 770118750.0,
      "talkgroup": 4499,
      "talkgroup_alpha_tag": "Avondale PD A01",
      "talkgroup_description": "A01 Dispatch",
      "talkgroup_group": "Avondale Police",
      "talkgroup_tag": "Law Dispatch",
      "elapsed": 4,
      "encrypted": false,
      "emergency": false,
      "phase2_tdma": true,
      "tdma_slot": 0,
      "rec_num": 0,
      "src_num": 0,
      "start_time": 1771215827
    }
  ],
  "timestamp": 1771215831,
  "instance_id": "trunk-recorder"
}
```

## Persistence (Postgres)

This contract assumes PR #1 schema exists:

- `tr_decode_rate_latest`
- `tr_recorders_snapshot_latest`
- `tr_calls_active_snapshot_latest`

For MVP, Emberlog API stores:

- latest decode rate per `(instance_id, sys_num)`
- latest recorders snapshot per `instance_id`
- latest calls_active snapshot per `instance_id`

## Normalization Rules

### Decode rate
MQTT `decoderate` appears as either:
- a percentage already (e.g., `41.0`), or
- a fraction (e.g., `0.33` meaning 33%)

**Rule:** if `decoderate <= 1.0`, multiply by 100; else use as-is.

Store both:
- `decoderate_raw` = original value
- `decoderate_pct` = normalized percent (0–100)

### Control channel / frequency
Inputs are floats in **Hz**. API outputs **MHz** for UI readability.

- `control_channel_mhz = control_channel_hz / 1_000_000`
- `freq_mhz = freq_hz / 1_000_000`

### Grouping System vs Site
Trunk Recorder uses `sys_name` as a combined **system+site** key (e.g., `PRWC-J`, `MCSO-WT`).

For UI grouping only:
- `group = sys_name.split("-")[0]` (prefix before first dash)

### Recorder ID
For calls, derive a consistent recorder id:
- `recorder_id = f"{src_num}_{rec_num}"`

## Health / Staleness (UI and API)

Traffic Monitor needs a simple “is the feed alive?” indicator.

**Definition:**  
`last_seen_at` = max(updated_at) across:
- latest rates (any row for instance)
- latest recorders snapshot (row for instance)
- latest calls_active snapshot (row for instance)

Suggested UI thresholds:
- **healthy**: `now - last_seen_at <= 10s`
- **degraded**: `10s < age <= 30s`
- **offline**: `age > 30s`

(Thresholds can be tuned later; MVP just needs last_seen_at.)

---

# API Endpoints

Base path: `/api/v1`

All endpoints return JSON.

## 1) GET `/api/v1/traffic/summary`

Purpose: returns all data needed to render the **top strip + decode grid**.

### Query params
- `instance_id` (optional, default: `"trunk-recorder"`)

### Response (200)

```json
{
  "instance_id": "trunk-recorder",
  "last_seen_at": "2026-02-16T04:23:51Z",
  "active_calls_count": 2,
  "recorders": {
    "total": 30,
    "recording": 2,
    "idle": 1,
    "available": 27,
    "updated_at": "2026-02-16T04:23:46Z"
  },
  "decode_groups": [
    {
      "group": "PRWC",
      "sites": [
        {
          "sys_num": 1,
          "sys_name": "PRWC-J",
          "decode_rate_pct": 41.0,
          "control_channel_mhz": 769.11875,
          "interval_s": 3.0,
          "updated_at": "2026-02-16T04:23:41Z",
          "status": "bad"
        }
      ]
    }
  ]
}
```

### Field notes
- `active_calls_count` comes from latest calls_active snapshot.
- `recorders.*` comes from latest recorders snapshot (derived counts).
- `decode_groups` is derived from `tr_decode_rate_latest` grouped by `group`.

### `status` classification for decode sites (MVP)
- `ok` if `decode_rate_pct >= 90`
- `warn` if `70 <= decode_rate_pct < 90`
- `bad` if `< 70`

(Thresholds can be configurable later.)

### Empty-data behavior
If no rows exist yet:
- Return `active_calls_count: 0`
- `recorders: null` (or zeroed counts) — pick one and be consistent
- `decode_groups: []`
- `last_seen_at: null`

Recommended MVP approach: allow `null` for `last_seen_at` and `recorders`.

---

## 2) GET `/api/v1/traffic/live-calls`

Purpose: returns normalized call rows for the **Live Calls table**.

### Query params
- `instance_id` (optional, default: `"trunk-recorder"`)
- `sys_name` (optional, repeatable or comma-separated; filter)
- `group` (optional; filter)
- `q` (optional; case-insensitive substring match against talkgroup alpha tag/description)

> Filtering can be MVP-lite: implement `sys_name` and `q` first if needed.

### Response (200)

```json
{
  "instance_id": "trunk-recorder",
  "updated_at": "2026-02-16T04:23:51Z",
  "calls": [
    {
      "id": "1_4499_1771215827",
      "started_at": "2026-02-16T04:23:47Z",
      "elapsed_s": 4,
      "system_site": "PRWC-J",
      "group": "PRWC",
      "talkgroup_id": 4499,
      "talkgroup": "Avondale PD A01",
      "description": "A01 Dispatch",
      "category": "Avondale Police",
      "tag": "Law Dispatch",
      "freq_mhz": 770.11875,
      "encrypted": false,
      "emergency": false,
      "phase2_tdma": true,
      "tdma_slot": 0,
      "unit": 707004,
      "recorder_id": "0_0"
    }
  ]
}
```

### Field mapping notes
- `system_site` = TR `sys_name`
- `group` = prefix before dash, e.g., `PRWC`
- `category` = TR `talkgroup_group`
- `tag` = TR `talkgroup_tag`
- `started_at` derived from TR `start_time` (epoch seconds) if present.
- `elapsed_s` = TR `elapsed`
- `unit` optional; include if present
- `recorder_id` derived from `src_num`/`rec_num`

### Empty-data behavior
If calls_active snapshot missing:
- Return `calls: []`
- `updated_at: null`

---

# Error Handling

- 500 only for unexpected server errors.
- If DB is reachable but there is simply no data yet, return 200 with empty/nulls as described above.
- If `instance_id` requested is unknown, return 200 with empty/nulls (MVP) rather than 404.

---

# Polling Recommendations (emberlog-web)

- Poll `traffic/summary` every **2 seconds**
- Poll `traffic/live-calls` every **2 seconds**
- If `last_seen_at` is null or stale beyond thresholds, show a banner:
  - “Traffic feed stale/offline”

---

# Implementation Notes for Scribe

1) Do **not** reintroduce websocket/SSE for this MVP.
2) Keep MQTT ingestion in a single background task started during FastAPI lifespan.
3) Use repository upsert helpers added in PR #1:
   - `upsert_decode_rate`
   - `upsert_recorders_snapshot`
   - `upsert_calls_active_snapshot`
4) Use structured logging and keep noisy logs at DEBUG.
5) Keep endpoints read-only; no mutations in this feature.
