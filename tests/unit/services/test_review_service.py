from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhunt.db import connect
from jobhunt.models import Decision, Job, RankResult
from jobhunt.repositories import ApplicationRepository, JobRepository
from jobhunt.services import ReviewService
from jobhunt.tailor import Tailor
from tests.unit._fakes import FakeLLMProvider, make_raw


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[tuple[JobRepository, ApplicationRepository]]:
    conn = connect(tmp_path / "review.sqlite")
    try:
        yield JobRepository(conn), ApplicationRepository(conn)
    finally:
        conn.close()


def _seed_shortlist(jobs: JobRepository, n: int = 3) -> list[Job]:
    now = datetime(2026, 4, 29, tzinfo=UTC)
    raws = [make_raw(idx=i) for i in range(n)]
    jobs_list = [Job.from_raw(r, fetched_at=now) for r in raws]
    jobs.save_many(jobs_list)
    for j, score in zip(jobs_list, [90, 70, 50], strict=True):
        jobs.update_score(j.id, RankResult(score=score, reason="ok"))
    jobs.mark_shortlisted([j.id for j in jobs_list])
    return jobs_list


def test_next_yields_only_pending_or_undecided(
    repos: tuple[JobRepository, ApplicationRepository],
) -> None:
    jobs, apps = repos
    seeded = _seed_shortlist(jobs)
    llm = FakeLLMProvider()
    service = ReviewService(jobs=jobs, applications=apps, tailor=Tailor(llm=llm, cv="CV"))
    items = list(service.next())
    assert {item.job.id for item in items} == {j.id for j in seeded}


def test_record_approved_triggers_tailor_and_persists_letter(
    repos: tuple[JobRepository, ApplicationRepository],
) -> None:
    jobs, apps = repos
    seeded = _seed_shortlist(jobs)
    llm = FakeLLMProvider(cover_letter="Sehr geehrte,\nbody")
    service = ReviewService(jobs=jobs, applications=apps, tailor=Tailor(llm=llm, cv="CV"))
    service.record(job_id=seeded[0].id, decision=Decision.APPROVED)
    assert len(llm.tailor_calls) == 1
    stored = apps.get(seeded[0].id)
    assert stored is not None
    assert stored.decision == Decision.APPROVED
    assert stored.cover_letter == "Sehr geehrte,\nbody"


def test_record_rejected_does_not_call_tailor(
    repos: tuple[JobRepository, ApplicationRepository],
) -> None:
    jobs, apps = repos
    seeded = _seed_shortlist(jobs)
    llm = FakeLLMProvider()
    service = ReviewService(jobs=jobs, applications=apps, tailor=Tailor(llm=llm, cv="CV"))
    service.record(job_id=seeded[0].id, decision=Decision.REJECTED)
    assert llm.tailor_calls == []
    assert apps.get(seeded[0].id) is not None


def test_recorded_jobs_not_yielded_again(
    repos: tuple[JobRepository, ApplicationRepository],
) -> None:
    jobs, apps = repos
    seeded = _seed_shortlist(jobs)
    llm = FakeLLMProvider()
    service = ReviewService(jobs=jobs, applications=apps, tailor=Tailor(llm=llm, cv="CV"))
    service.record(job_id=seeded[0].id, decision=Decision.REJECTED)
    remaining = list(service.next())
    assert seeded[0].id not in {item.job.id for item in remaining}
