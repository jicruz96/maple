import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Mapping,
    Optional,
    ParamSpec,
    Sequence,
    TypeVar,
)

import httpx
from rich import print


async def _log_response(res: httpx.Response) -> None:
    print(f"[http] {res.request.method} {res.request.url} -> {res.status_code}")


_client_override: ContextVar[Optional[httpx.AsyncClient]] = ContextVar(
    "httpx_client_override", default=None
)


def create_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
        event_hooks={
            "response": [_log_response],
        },
    )


def get_client() -> httpx.AsyncClient:
    """Return the current context-scoped HTTP client.

    Requires being inside `lifespan()` or having set an override explicitly.
    Raises a RuntimeError if called outside a managed context to avoid leaking
    a global client that callers might forget to close.
    """
    override = _client_override.get()
    if override is None:
        raise RuntimeError(
            "No HTTP client found in context. Wrap your call in `async with "
            "lifespan(): ...` or decorate your click command with "
            "`@run_in_lifespan`."
        )
    return override


async def http_get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    raise_on_status_except_for: Sequence[int] | None = None,
) -> httpx.Response:
    resp = await get_client().get(url, headers=headers, params=params)
    if not resp.is_success and resp.status_code not in set(
        raise_on_status_except_for or []
    ):
        resp.raise_for_status()
    return resp


@asynccontextmanager
async def lifespan() -> AsyncIterator[httpx.AsyncClient]:
    """Provide a per-context client set in a ContextVar and close on exit.

    Useful for tests or wrapping a whole command without relying on globals.
    """
    client = create_client()
    token = _client_override.set(client)
    try:
        yield client
    finally:
        _client_override.reset(token)
        await client.aclose()


T = TypeVar("T")
P = ParamSpec("P")


def run_in_lifespan(func: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    @wraps(func)
    def _runner(*args: P.args, **kwargs: P.kwargs) -> T:
        async def _wrap() -> T:
            async with lifespan():
                return await func(*args, **kwargs)

        return asyncio.run(_wrap())

    return _runner
