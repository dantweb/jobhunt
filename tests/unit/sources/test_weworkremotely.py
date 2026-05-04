from __future__ import annotations

import httpx

from jobhunt.sources.weworkremotely import WeWorkRemotelySource
from tests.unit.sources._helpers import client_with_handler, load_text_fixture


def test_rss_parses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=load_text_fixture("weworkremotely_sample.xml"))

    with client_with_handler(handler) as client:
        results = list(WeWorkRemotelySource(http_client=client).fetch())

    assert len(results) == 2
    assert results[0].company == "ACME GmbH"
    assert results[0].title == "Senior Python Engineer"
    assert results[0].language == "en"


def test_missing_optional_fields_default_to_none() -> None:
    feed = """<?xml version="1.0"?><rss><channel>
        <item><title>OnlyTitle</title><link>https://x.example/1</link></item>
    </channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=feed)

    with client_with_handler(handler) as client:
        results = list(WeWorkRemotelySource(http_client=client).fetch())

    assert len(results) == 1
    assert results[0].posted_at is None
    assert results[0].description is None
