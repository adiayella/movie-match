import os
import time

import httpx
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

_client: Client | None = None

# Raised when a pooled keep-alive connection turns out to be dead, or the
# network hiccups mid-request. All are safe to retry here: every query this
# app makes is either a read or an idempotent upsert.
_RETRYABLE = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
)


def _install_retry(session: httpx.Client, attempts: int = 3) -> None:
    """Retry PostgREST calls that fail on a stale pooled connection.

    Supabase's client holds long-lived keep-alive connections. When one goes
    stale (idle a while, or closed by the far end) the next request through
    it raises RemoteProtocolError("Server disconnected") rather than
    transparently reconnecting. That surfaced as random mid-session 500s --
    and since an unhandled 500 never reaches the CORS middleware, the browser
    reported it only as a bare "Failed to fetch"/"Load failed" a few swipes in.
    Retrying picks up a fresh connection, since httpcore evicts the broken one.
    """
    original = session.request

    def request_with_retry(*args, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return original(*args, **kwargs)
            except _RETRYABLE as exc:
                last_exc = exc
                time.sleep(0.15 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    session.request = request_with_retry  # type: ignore[method-assign]


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        session = getattr(_client.postgrest, "session", None)
        if isinstance(session, httpx.Client):
            _install_retry(session)
    return _client
