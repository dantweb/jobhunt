"""Helpers for source-adapter tests: fixture loading + factories."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx

from jobhunt.sources import (
    AdzunaSource,
    ArbeitnowSource,
    BundesagenturSource,
    JobSource,
    JoobleSource,
    RemotiveSource,
    WeWorkRemotelySource,
)
from jobhunt.sources._http import RetryOn5xxTransport

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def load_json_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES_DIR / name).read_text())


def load_text_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """Build a real `httpx.Client` whose underlying transport is a MockTransport
    wrapped in our retry layer — exercises the retry logic when the handler
    returns 5xx, otherwise returns the canned response untouched.
    """
    inner = httpx.MockTransport(handler)
    transport = RetryOn5xxTransport(retries=1, inner=inner)
    return httpx.Client(transport=transport)


def make_source_with_stub_creds(source_cls: type[JobSource], client: httpx.Client) -> JobSource:
    if source_cls is BundesagenturSource:
        return BundesagenturSource(http_client=client)
    if source_cls is ArbeitnowSource:
        return ArbeitnowSource(http_client=client)
    if source_cls is AdzunaSource:
        return AdzunaSource(app_id="stub-id", app_key="stub-key", http_client=client)
    if source_cls is JoobleSource:
        return JoobleSource(api_key="stub-key", http_client=client)
    if source_cls is RemotiveSource:
        return RemotiveSource(http_client=client)
    if source_cls is WeWorkRemotelySource:
        return WeWorkRemotelySource(http_client=client)
    raise AssertionError(f"unknown source class: {source_cls}")


def canned_handler_for(source_cls: type[JobSource]) -> Callable[[httpx.Request], httpx.Response]:
    if source_cls is BundesagenturSource:

        def handle_bundesagentur(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=load_json_fixture("bundesagentur_sample.json"))

        return handle_bundesagentur
    if source_cls is ArbeitnowSource:

        def handle_arbeitnow(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=load_json_fixture("arbeitnow_sample.json"))

        return handle_arbeitnow
    if source_cls is AdzunaSource:

        def handle_adzuna(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=load_json_fixture("adzuna_sample.json"))

        return handle_adzuna
    if source_cls is JoobleSource:

        def handle_jooble(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=load_json_fixture("jooble_sample.json"))

        return handle_jooble
    if source_cls is RemotiveSource:

        def handle_remotive(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=load_json_fixture("remotive_sample.json"))

        return handle_remotive
    if source_cls is WeWorkRemotelySource:

        def handle_wwr(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=load_text_fixture("weworkremotely_sample.xml"))

        return handle_wwr
    raise AssertionError(f"unknown source class: {source_cls}")
