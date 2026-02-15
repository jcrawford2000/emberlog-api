"""Helpers for safe logging of headers and optional payload previews."""

from collections.abc import Mapping

from emberlog_api.app.core.settings import settings

_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Return headers with known sensitive values redacted."""
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADERS:
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted


def payload_preview(payload: str) -> str | None:
    """Return a bounded payload preview when debug previewing is enabled."""
    if not settings.log_payload_preview:
        return None
    preview = payload[: settings.log_payload_max_chars]
    if len(payload) > settings.log_payload_max_chars:
        return f"{preview}..."
    return preview
