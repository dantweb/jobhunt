from __future__ import annotations

import httpx
import pytest

from jobhunt.exceptions import MissingCredentialsError
from jobhunt.sources.jooble import JoobleSource
from tests.unit.sources._helpers import client_with_handler, load_json_fixture


def test_happy_path_with_creds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=load_json_fixture("jooble_sample.json"))

    with client_with_handler(handler) as client:
        results = list(JoobleSource(api_key="key", http_client=client).fetch())
    assert len(results) == 2
    assert results[0].source == "jooble"


def test_missing_key_raises_before_network() -> None:
    network_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        network_calls["n"] += 1
        return httpx.Response(200, json={"jobs": []})

    with client_with_handler(handler) as client, pytest.raises(MissingCredentialsError):
        JoobleSource(api_key="", http_client=client)

    assert network_calls["n"] == 0
