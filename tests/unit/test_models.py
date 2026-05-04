from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jobhunt.models import (
    ALLOWED_FLAGS,
    Application,
    Decision,
    Delivery,
    Filters,
    Job,
    ProfileDraft,
    RankResult,
    RawPosting,
)


class TestDedupeHash:
    def test_same_canonical_fields_produce_same_hash(self) -> None:
        a = Job.dedupe_hash(title="Senior Python Engineer", company="ACME", location="Berlin")
        b = Job.dedupe_hash(title="Senior Python Engineer", company="ACME", location="Berlin")
        assert a == b

    def test_normalisation_collapses_whitespace_and_case(self) -> None:
        a = Job.dedupe_hash(title="  Senior   Python  Engineer ", company="ACME", location="Berlin")
        b = Job.dedupe_hash(title="senior python engineer", company="acme", location="berlin")
        assert a == b

    def test_different_companies_produce_different_hashes(self) -> None:
        a = Job.dedupe_hash(title="t", company="A", location="X")
        b = Job.dedupe_hash(title="t", company="B", location="X")
        assert a != b

    def test_none_location_treated_as_empty_string(self) -> None:
        a = Job.dedupe_hash(title="t", company="C", location=None)
        b = Job.dedupe_hash(title="t", company="C", location="")
        assert a == b

    def test_two_sources_for_same_posting_produce_same_id(self) -> None:
        raw_a = RawPosting(
            external_id="bundes-42",
            title="Senior Python Engineer",
            company="ACME",
            url="https://a.example/1",
            source="bundesagentur",
            location="Berlin",
        )
        raw_b = RawPosting(
            external_id="arbnow-99",
            title="Senior Python Engineer",
            company="ACME",
            url="https://b.example/2",
            source="arbeitnow",
            location="Berlin",
        )
        ts = datetime(2026, 4, 29, tzinfo=UTC)
        assert Job.from_raw(raw_a, fetched_at=ts).id == Job.from_raw(raw_b, fetched_at=ts).id


class TestFilters:
    def test_negative_salary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Filters(
                min_salary_eur=-1,
                allowed_locations=["remote"],
                seniority=["senior"],
                stack_must_haves=["python"],
            )

    def test_empty_allowed_locations_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Filters(
                min_salary_eur=0,
                allowed_locations=[],
                seniority=["senior"],
                stack_must_haves=["python"],
            )

    def test_empty_seniority_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Filters(
                min_salary_eur=0,
                allowed_locations=["remote"],
                seniority=[],
                stack_must_haves=["python"],
            )

    def test_empty_stack_must_haves_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Filters(
                min_salary_eur=0,
                allowed_locations=["remote"],
                seniority=["senior"],
                stack_must_haves=[],
            )


class TestRankResult:
    def test_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankResult(score=-1, reason="x")

    def test_score_above_hundred_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankResult(score=101, reason="x")

    def test_unknown_flag_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankResult(score=50, reason="x", flags=frozenset({"not_a_real_flag"}))

    def test_allowed_flags_accepted(self) -> None:
        result = RankResult(score=80, reason="solid match", flags=ALLOWED_FLAGS)
        assert result.flags == ALLOWED_FLAGS

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RankResult(score=50, reason="")

    def test_flags_default_to_empty_set(self) -> None:
        result = RankResult(score=50, reason="ok")
        assert result.flags == frozenset()


class TestProfileDraft:
    def test_round_trip_to_filters(self) -> None:
        draft = ProfileDraft(
            min_salary_eur=85000,
            allowed_locations=["remote", "berlin"],
            language_preference="en",
            language_fallback="de",
            seniority=["senior"],
            stack_must_haves=["python", "rust"],
        )
        filters = draft.to_filters()
        assert isinstance(filters, Filters)
        assert filters.min_salary_eur == 85000
        assert filters.stack_must_haves == ["python", "rust"]

    def test_defaults_are_useful(self) -> None:
        draft = ProfileDraft()
        assert draft.allowed_locations == ["remote"]
        assert draft.seniority == ["senior"]
        assert draft.language_preference == "en"


class TestApplication:
    def test_default_decision_is_pending(self) -> None:
        app = Application(job_id="abc")
        assert app.decision == Decision.PENDING
        assert app.delivery is None

    def test_delivery_enum_values(self) -> None:
        assert Delivery.EMAIL.value == "email"
        assert Delivery.BROWSER.value == "browser"
