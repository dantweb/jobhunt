from __future__ import annotations

import httpx
import pytest

from jobhunt.sources._http import RetryOn5xxTransport, make_client


def _make_test_client(handler):  # type: ignore[no-untyped-def]
    inner = httpx.MockTransport(handler)
    return httpx.Client(transport=RetryOn5xxTransport(retries=1, inner=inner))


class TestRetry:
    def test_5xx_then_200_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503)
            return httpx.Response(200, json={"ok": True})

        with _make_test_client(handler) as client:
            response = client.get("https://example.com/x")
        assert response.status_code == 200
        assert calls["n"] == 2

    def test_two_5xx_returns_last_5xx(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        with _make_test_client(handler) as client:
            response = client.get("https://example.com/x")
        assert response.status_code == 503
        assert calls["n"] == 2

    def test_4xx_not_retried(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(404)

        with _make_test_client(handler) as client:
            response = client.get("https://example.com/x")
        assert response.status_code == 404
        assert calls["n"] == 1


class TestMakeClient:
    def test_default_user_agent_set(self) -> None:
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["ua"] = request.headers.get("user-agent", "")
            return httpx.Response(200)

        inner = httpx.MockTransport(handler)
        client = make_client(transport=inner)
        try:
            client.get("https://example.com/")
        finally:
            client.close()
        assert "jobhunt" in captured["ua"]

    def test_custom_headers_merged(self) -> None:
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["x-key"] = request.headers.get("x-api-key", "")
            return httpx.Response(200)

        inner = httpx.MockTransport(handler)
        client = make_client(transport=inner, headers={"X-API-Key": "abc"})
        try:
            client.get("https://example.com/")
        finally:
            client.close()
        assert captured["x-key"] == "abc"

    def test_timeout_raises_on_slow_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        inner = httpx.MockTransport(handler)
        client = make_client(transport=inner)
        with pytest.raises(httpx.ReadTimeout):
            try:
                client.get("https://example.com/")
            finally:
                client.close()
