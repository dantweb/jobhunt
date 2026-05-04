from __future__ import annotations

import httpx

from jobhunt.sources.arbeitnow import ArbeitnowSource
from tests.unit.sources._helpers import client_with_handler, load_json_fixture


def test_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load_json_fixture("arbeitnow_sample.json"))

    with client_with_handler(handler) as client:
        results = list(ArbeitnowSource(http_client=client).fetch())

    assert len(results) == 2
    assert results[0].source == "arbeitnow"
    assert results[0].language == "en"  # tagged english


def test_empty_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "links": {"next": None}})

    with client_with_handler(handler) as client:
        results = list(ArbeitnowSource(http_client=client).fetch())

    assert results == []


def test_unknown_extra_field_tolerated() -> None:
    payload = {
        "data": [
            {
                "id": "x",
                "slug": "x",
                "title": "Engineer",
                "company_name": "Co",
                "url": "https://x.example",
                "description": "...",
                "location": "Berlin",
                "tags": ["english"],
                "created_at": 1745116800,
                "future_field_we_dont_know_about": "hello",
            }
        ],
        "links": {"next": None},
        "meta": {"total": 1},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with client_with_handler(handler) as client:
        results = list(ArbeitnowSource(http_client=client).fetch())

    assert len(results) == 1
    assert results[0].title == "Engineer"
