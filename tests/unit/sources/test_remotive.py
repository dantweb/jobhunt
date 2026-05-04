from __future__ import annotations

import httpx

from jobhunt.sources.remotive import RemotiveSource
from tests.unit.sources._helpers import client_with_handler, load_json_fixture


def test_filters_out_non_eu_postings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load_json_fixture("remotive_sample.json"))

    with client_with_handler(handler) as client:
        results = list(RemotiveSource(http_client=client).fetch())

    locations = {r.location for r in results}
    assert "USA" not in locations
    assert any(loc and loc.lower() == "europe" for loc in locations)


def test_happy_path_returns_required_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load_json_fixture("remotive_sample.json"))

    with client_with_handler(handler) as client:
        results = list(RemotiveSource(http_client=client).fetch())
    assert all(r.external_id for r in results)
    assert all(r.title for r in results)
    assert all(r.company for r in results)
    assert all(r.url for r in results)
