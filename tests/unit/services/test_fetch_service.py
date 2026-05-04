from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from jobhunt.db import connect
from jobhunt.models import Filters, RankResult
from jobhunt.ranker import Ranker
from jobhunt.repositories import JobRepository
from jobhunt.services import FetchService
from tests.unit._fakes import FakeJobSource, FakeLLMProvider, make_raw


@pytest.fixture
def jobs_repo(tmp_path: Path) -> Iterator[JobRepository]:
    conn = connect(tmp_path / "fetch.sqlite")
    try:
        yield JobRepository(conn)
    finally:
        conn.close()


def _filters() -> Filters:
    return Filters(
        min_salary_eur=0,
        allowed_locations=["remote"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )


def test_fetches_from_each_source_and_saves(jobs_repo: JobRepository) -> None:
    src_a = FakeJobSource(
        [
            make_raw(idx=1, source="src_a"),
            make_raw(idx=2, source="src_a"),
        ],
        name="src_a",
    )
    src_b = FakeJobSource([make_raw(idx=3, source="src_b")], name="src_b")
    llm = FakeLLMProvider(rank_result=RankResult(score=80, reason="ok"))
    ranker = Ranker(llm=llm, filters=_filters(), cv="CV")
    service = FetchService(sources=[src_a, src_b], jobs=jobs_repo, ranker=ranker, shortlist_size=20)
    report = service.run()
    assert report.fetched_per_source == {"src_a": 2, "src_b": 1}
    assert report.saved == 3


def test_failure_in_one_source_does_not_abort(jobs_repo: JobRepository) -> None:
    bad = FakeJobSource([], raises=RuntimeError("boom"))
    good = FakeJobSource([make_raw(idx=1, title="Senior Python Engineer")])
    llm = FakeLLMProvider(rank_result=RankResult(score=70, reason="ok"))
    ranker = Ranker(llm=llm, filters=_filters(), cv="CV")
    service = FetchService(sources=[bad, good], jobs=jobs_repo, ranker=ranker, shortlist_size=20)
    report = service.run()
    assert "boom" in report.failures["fake"]
    assert report.saved == 1


def test_shortlist_top_n_by_score(jobs_repo: JobRepository) -> None:
    sources = [
        FakeJobSource([make_raw(idx=i, title=f"Senior Python Engineer {i}") for i in range(5)])
    ]

    class StaticLLM(FakeLLMProvider):
        scores = iter([10, 90, 50, 70, 30])

        def rank(self, job, cv, filters):  # type: ignore[no-untyped-def]
            return RankResult(score=next(StaticLLM.scores), reason="ok")

    ranker = Ranker(llm=StaticLLM(), filters=_filters(), cv="CV")
    service = FetchService(sources=sources, jobs=jobs_repo, ranker=ranker, shortlist_size=2)
    report = service.run()
    assert report.shortlisted == 2
    shortlisted = jobs_repo.shortlisted()
    assert {j.score for j in shortlisted} == {90, 70}
