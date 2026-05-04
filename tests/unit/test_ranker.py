from __future__ import annotations

from datetime import UTC, datetime

from jobhunt.filters import LocationAllowlistRule, SalaryFloorRule
from jobhunt.models import Filters, Job, RankResult, RawPosting
from jobhunt.ranker import Ranker
from tests.unit._fakes import FakeLLMProvider


def _job(**fields: object) -> Job:
    raw = RawPosting(
        external_id="x",
        title=str(fields.pop("title", "Senior Python Engineer")),
        company="ACME",
        url="https://x",
        source="test",
        description=fields.pop("description", None),  # type: ignore[arg-type]
        location=fields.pop("location", "Remote"),  # type: ignore[arg-type]
        language=fields.pop("language", "en"),  # type: ignore[arg-type]
        salary_min_eur=fields.pop("salary_min_eur", None),  # type: ignore[arg-type]
        salary_max_eur=fields.pop("salary_max_eur", None),  # type: ignore[arg-type]
    )
    assert not fields
    return Job.from_raw(raw, fetched_at=datetime(2026, 4, 29, tzinfo=UTC))


def _filters() -> Filters:
    return Filters(
        min_salary_eur=90000,
        allowed_locations=["remote", "karlsruhe"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )


def test_score_short_circuits_on_reject_no_llm_call() -> None:
    llm = FakeLLMProvider()
    ranker = Ranker(
        llm=llm,
        filters=_filters(),
        cv="CV",
        rules=(SalaryFloorRule(), LocationAllowlistRule()),
    )
    result = ranker.score(_job(salary_max_eur=50000))
    assert result is None
    assert llm.rank_calls == []


def test_score_calls_llm_when_all_rules_pass() -> None:
    llm = FakeLLMProvider(rank_result=RankResult(score=85, reason="great"))
    ranker = Ranker(llm=llm, filters=_filters(), cv="CV")
    result = ranker.score(_job(salary_max_eur=120000))
    assert result is not None
    assert result.score == 85
    assert len(llm.rank_calls) == 1


def test_score_merges_rule_flags_with_llm_flags() -> None:
    llm = FakeLLMProvider(
        rank_result=RankResult(score=70, reason="ok", flags=frozenset({"location_mismatch"}))
    )
    ranker = Ranker(llm=llm, filters=_filters(), cv="CV")
    # Job has missing salary → adds salary_unstated rule flag.
    result = ranker.score(_job())
    assert result is not None
    assert "location_mismatch" in result.flags
    assert "salary_unstated" in result.flags


def test_score_many_drops_rejects() -> None:
    llm = FakeLLMProvider(rank_result=RankResult(score=70, reason="ok"))
    ranker = Ranker(llm=llm, filters=_filters(), cv="CV")
    jobs = [
        _job(title="Senior Python", salary_max_eur=120000),
        _job(title="Senior Go", salary_max_eur=50000, description=""),
    ]
    scored = ranker.score_many(jobs)
    assert len(scored) == 1


def test_short_circuit_for_each_default_rule_kind() -> None:
    """Each rule type, when broken, prevents the LLM call."""
    llm = FakeLLMProvider()
    ranker = Ranker(
        llm=llm,
        filters=_filters(),
        cv="CV",
        rules=(SalaryFloorRule(),),
    )
    ranker.score(_job(salary_max_eur=10000))
    ranker.score(_job(salary_max_eur=20000))
    assert llm.rank_calls == []
