"""Integration test: real SQLite, real schema, real repositories end-to-end."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jobhunt.db import connect
from jobhunt.exceptions import InvalidStateTransitionError, JobNotFoundError
from jobhunt.models import Application, Decision, Delivery, Job, RankResult, RawPosting
from jobhunt.repositories import ApplicationRepository, JobRepository


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "integration.sqlite"
    connection = connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def _make_job(*, idx: int, fetched_at: datetime, source: str = "bundesagentur") -> Job:
    raw = RawPosting(
        external_id=f"ext-{idx}",
        title=f"Engineer Role {idx}",
        company=f"Company {idx}",
        url=f"https://example.com/{idx}",
        source=source,
        location="Berlin",
    )
    return Job.from_raw(raw, fetched_at=fetched_at)


def test_connect_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "i.sqlite"
    c1 = connect(db_path)
    c1.close()
    c2 = connect(db_path)
    c2.close()


def test_save_many_returns_inserted_count(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    jobs = [_make_job(idx=i, fetched_at=now) for i in range(3)]
    assert repo.save_many(jobs) == 3


def test_save_many_is_idempotent(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    jobs = [_make_job(idx=i, fetched_at=now) for i in range(3)]
    repo.save_many(jobs)
    assert repo.save_many(jobs) == 0


def test_save_many_dedupes_across_sources(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    job_a = _make_job(idx=1, fetched_at=now, source="bundesagentur")
    job_b = _make_job(idx=1, fetched_at=now, source="arbeitnow")
    assert job_a.id == job_b.id  # same dedupe hash
    inserted_first = repo.save_many([job_a])
    inserted_second = repo.save_many([job_b])
    assert inserted_first == 1
    assert inserted_second == 0


def test_save_many_mixed_batch(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    initial = [_make_job(idx=i, fetched_at=now) for i in range(2)]
    repo.save_many(initial)
    next_batch = initial + [_make_job(idx=i, fetched_at=now) for i in range(2, 5)]
    assert repo.save_many(next_batch) == 3


def test_get_returns_job(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    job = _make_job(idx=1, fetched_at=now)
    repo.save_many([job])
    fetched = repo.get(job.id)
    assert fetched.id == job.id
    assert fetched.title == job.title


def test_get_missing_raises(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    with pytest.raises(JobNotFoundError):
        repo.get("does-not-exist")


def test_update_score_and_shortlist(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    jobs = [_make_job(idx=i, fetched_at=now) for i in range(5)]
    repo.save_many(jobs)
    for j, score in zip(jobs, [10, 90, 50, 70, 30], strict=True):
        repo.update_score(j.id, RankResult(score=score, reason="ok"))
    repo.mark_shortlisted([j.id for j in jobs])
    top_two = repo.shortlisted(limit=2)
    assert [j.score for j in top_two] == [90, 70]


def test_mark_shortlisted_replaces_previous_set(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    jobs = [_make_job(idx=i, fetched_at=now) for i in range(3)]
    repo.save_many(jobs)
    for j in jobs:
        repo.update_score(j.id, RankResult(score=50, reason="ok"))
    repo.mark_shortlisted([jobs[0].id, jobs[1].id])
    assert {j.id for j in repo.shortlisted()} == {jobs[0].id, jobs[1].id}
    repo.mark_shortlisted([jobs[2].id])
    assert {j.id for j in repo.shortlisted()} == {jobs[2].id}


def test_unscored_returns_only_unscored(conn: sqlite3.Connection) -> None:
    repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    jobs = [_make_job(idx=i, fetched_at=now) for i in range(3)]
    repo.save_many(jobs)
    repo.update_score(jobs[0].id, RankResult(score=50, reason="ok"))
    unscored = repo.unscored()
    assert {j.id for j in unscored} == {jobs[1].id, jobs[2].id}


def test_application_record_decision_is_upsert(conn: sqlite3.Connection) -> None:
    repos = ApplicationRepository(conn)
    job_repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    job = _make_job(idx=1, fetched_at=now)
    job_repo.save_many([job])
    repos.record_decision(Application(job_id=job.id, decision=Decision.PENDING))
    repos.record_decision(Application(job_id=job.id, decision=Decision.APPROVED))
    fetched = repos.get(job.id)
    assert fetched is not None
    assert fetched.decision == Decision.APPROVED


def test_mark_sent_only_on_approved(conn: sqlite3.Connection) -> None:
    apps = ApplicationRepository(conn)
    job_repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    job = _make_job(idx=1, fetched_at=now)
    job_repo.save_many([job])
    apps.record_decision(Application(job_id=job.id, decision=Decision.REJECTED))
    with pytest.raises(InvalidStateTransitionError):
        apps.mark_sent(job.id, now, Delivery.EMAIL)


def test_mark_sent_on_unknown_job_raises(conn: sqlite3.Connection) -> None:
    apps = ApplicationRepository(conn)
    with pytest.raises(JobNotFoundError):
        apps.mark_sent("no-such-job", datetime.now(tz=UTC), Delivery.EMAIL)


def test_mark_sent_succeeds_for_approved(conn: sqlite3.Connection) -> None:
    apps = ApplicationRepository(conn)
    job_repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    job = _make_job(idx=1, fetched_at=now)
    job_repo.save_many([job])
    apps.record_decision(Application(job_id=job.id, decision=Decision.APPROVED))
    apps.mark_sent(job.id, now, Delivery.EMAIL)
    fetched = apps.get(job.id)
    assert fetched is not None
    assert fetched.delivery == Delivery.EMAIL
    assert fetched.sent_at is not None


def test_emails_sent_in_last_24h(conn: sqlite3.Connection) -> None:
    apps = ApplicationRepository(conn)
    job_repo = JobRepository(conn)
    now = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)
    long_ago = now - timedelta(hours=48)
    recent = now - timedelta(hours=1)
    jobs = [_make_job(idx=i, fetched_at=now) for i in range(3)]
    job_repo.save_many(jobs)
    for j in jobs:
        apps.record_decision(Application(job_id=j.id, decision=Decision.APPROVED))
    apps.mark_sent(jobs[0].id, long_ago, Delivery.EMAIL)
    apps.mark_sent(jobs[1].id, recent, Delivery.EMAIL)
    apps.mark_sent(jobs[2].id, recent, Delivery.BROWSER)
    assert apps.emails_sent_in_last_24h(now=now) == 1


def test_pending_and_approved_filters(conn: sqlite3.Connection) -> None:
    apps = ApplicationRepository(conn)
    job_repo = JobRepository(conn)
    now = datetime(2026, 4, 29, tzinfo=UTC)
    jobs = [_make_job(idx=i, fetched_at=now) for i in range(3)]
    job_repo.save_many(jobs)
    apps.record_decision(Application(job_id=jobs[0].id, decision=Decision.PENDING))
    apps.record_decision(Application(job_id=jobs[1].id, decision=Decision.APPROVED))
    apps.record_decision(Application(job_id=jobs[2].id, decision=Decision.REJECTED))
    assert {a.job_id for a in apps.pending()} == {jobs[0].id}
    assert {a.job_id for a in apps.approved()} == {jobs[1].id}
