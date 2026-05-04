from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhunt.db import connect
from jobhunt.models import Filters, Job, RawPosting


@pytest.fixture
def tmp_db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_path / "test.sqlite")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 4, 29, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_raw() -> RawPosting:
    return RawPosting(
        external_id="ext-1",
        title="Senior Python Engineer",
        company="ACME GmbH",
        url="https://example.com/job/1",
        source="bundesagentur",
        description="We are hiring a senior Python engineer.",
        salary_min_eur=95000,
        salary_max_eur=120000,
        location="Remote",
        language="en",
        contact_email="jobs@example.com",
        apply_url=None,
    )


@pytest.fixture
def sample_job(sample_raw: RawPosting, now: datetime) -> Job:
    return Job.from_raw(sample_raw, fetched_at=now)


@pytest.fixture
def default_filters() -> Filters:
    return Filters(
        min_salary_eur=90000,
        allowed_locations=["remote", "karlsruhe", "frankfurt", "munich", "eu-remote"],
        language_preference="en",
        language_fallback="de",
        seniority=["senior", "lead", "staff", "principal"],
        stack_must_haves=["php", "symfony", "python"],
        shortlist_size=20,
    )
