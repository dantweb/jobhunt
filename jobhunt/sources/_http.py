"""Single shared HTTP client factory used by every source adapter."""

from __future__ import annotations

import httpx

DEFAULT_USER_AGENT = "jobhunt/0.1 (+https://github.com/jobhunt-cli/jobhunt)"
DEFAULT_TIMEOUT = 10.0


class RetryOn5xxTransport(httpx.BaseTransport):
    """Wraps an inner transport. Retries on 5xx responses up to `retries` times.

    No retry on 4xx, no retry on connection errors — fail loudly.
    """

    def __init__(self, *, retries: int = 1, inner: httpx.BaseTransport) -> None:
        self._retries = retries
        self._inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        last_response: httpx.Response | None = None
        for attempt in range(self._retries + 1):
            response = self._inner.handle_request(request)
            if response.status_code < 500 or response.status_code >= 600:
                return response
            last_response = response
            if attempt < self._retries:
                response.close()
        assert last_response is not None
        return last_response


def make_client(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
    transport: httpx.BaseTransport | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Client:
    inner = transport or httpx.HTTPTransport()
    retry_transport = RetryOn5xxTransport(retries=1, inner=inner)
    final_headers = {"User-Agent": user_agent, **(headers or {})}
    return httpx.Client(
        timeout=timeout,
        transport=retry_transport,
        headers=final_headers,
    )
