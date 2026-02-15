"""Context variable helpers for request and websocket correlation IDs."""

from contextvars import ContextVar, Token


_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_conn_id_var: ContextVar[str] = ContextVar("conn_id", default="-")


def get_request_id() -> str:
    """Return the active request identifier."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> Token[str]:
    """Set request identifier for current execution context."""
    return _request_id_var.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Reset request identifier to prior context value."""
    _request_id_var.reset(token)


def get_conn_id() -> str:
    """Return the active websocket connection identifier."""
    return _conn_id_var.get()


def set_conn_id(conn_id: str) -> Token[str]:
    """Set websocket connection identifier for current execution context."""
    return _conn_id_var.set(conn_id)


def reset_conn_id(token: Token[str]) -> None:
    """Reset websocket connection identifier to prior context value."""
    _conn_id_var.reset(token)
