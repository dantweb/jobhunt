from __future__ import annotations

import httpx

from jobhunt.sources.bundesagentur import BundesagenturSource
from tests.unit.sources._helpers import client_with_handler, load_json_fixture


def test_happy_path_yields_postings() -> None:
    handler_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        handler_calls["n"] += 1
        return httpx.Response(200, json=load_json_fixture("bundesagentur_sample.json"))

    with client_with_handler(handler) as client:
        source = BundesagenturSource(http_client=client)
        results = list(source.fetch())

    assert len(results) == 2
    assert results[0].title == "Senior Python Engineer"
    assert results[0].source == "bundesagentur"
    assert results[0].language == "de"
    assert results[0].location == "Karlsruhe"


def test_empty_first_page_stops_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"stellenangebote": []})

    with client_with_handler(handler) as client:
        results = list(BundesagenturSource(http_client=client).fetch())

    assert results == []


def test_5xx_then_success_retries_once() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"stellenangebote": []})

    with client_with_handler(handler) as client:
        list(BundesagenturSource(http_client=client).fetch())

    assert calls["n"] == 2
