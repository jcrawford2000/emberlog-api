# Emberlog-API Logging

This service uses stdlib logging with environment-controlled formatting and correlation IDs.

## Environment Variables

- `LOG_FORMAT`:
  - `auto` (default): `json` in `EMBERLOG_ENV=prod`, `console` otherwise
  - `json`: force JSON logs
  - `console`: force human-readable logs
- `LOG_PAYLOAD_PREVIEW`:
  - `false` (default)
  - when `true`, websocket message preview logging is enabled at DEBUG level
- `LOG_PAYLOAD_MAX_CHARS`:
  - max preview length for websocket payloads
  - default `256`

## Correlation IDs

- HTTP middleware reads `X-Request-ID` if present, otherwise generates a UUID.
- `X-Request-ID` is returned in HTTP responses.
- Request logs include request method, path, status, duration, and client IP.
- Websocket connections include a generated `conn_id` per connection for lifecycle logging.

## Websocket Logging Scope

For `WS /api/v1/stats/trunkrecorder/ws`, lifecycle logs include:

- `ws_connect`
- `ws_accept`
- `ws_message` (type + byte size only)
- `ws_error`
- `ws_disconnect` (duration + close code/reason)

Payloads are not logged by default.

## Manual Verification

HTTP:

```bash
curl -i http://localhost:8000/healthz
curl -i -H "X-Request-ID: demo-req-1" http://localhost:8000/readyz
```

Websocket:

```bash
websocat -v ws://localhost:8000/api/v1/stats/trunkrecorder/ws
{"type":"rates","instanceId":"trunkrecorder-default"}
```
