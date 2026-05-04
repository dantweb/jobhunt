"""The Liskov contract test for `JobSource` — runs against every entry in REGISTRY.

A new source cannot merge until it passes this suite.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from jobhunt.models import RawPosting
from jobhunt.sources import REGISTRY, JobSource
from tests.unit.sources._helpers import (
    canned_handler_for,
    client_with_handler,
    make_source_with_stub_creds,
)


@pytest.mark.parametrize("source_name", sorted(REGISTRY.keys()))
def test_fetch_returns_iterable_of_raw_posting(source_name: str) -> None:
    source_cls = REGISTRY[source_name]
    handler = canned_handler_for(source_cls)
    with client_with_handler(handler) as client:
        source: JobSource = make_source_with_stub_creds(source_cls, client)
        results = source.fetch()
        materialised: list[RawPosting] = list(results)

    assert isinstance(materialised, Iterable)
    assert len(materialised) >= 1
    for posting in materialised:
        assert isinstance(posting, RawPosting)
        # Every required field present and non-empty.
        assert posting.external_id
        assert posting.title
        assert posting.company
        assert posting.url
        assert posting.source == source_name


def test_registry_contains_six_default_sources() -> None:
    assert set(REGISTRY.keys()) == {
        "bundesagentur",
        "arbeitnow",
        "adzuna",
        "jooble",
        "remotive",
        "weworkremotely",
    }
