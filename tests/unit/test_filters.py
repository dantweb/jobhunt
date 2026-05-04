from __future__ import annotations

from datetime import UTC, datetime

from jobhunt.filters import (
    LanguageRule,
    LocationAllowlistRule,
    Pass,
    Reject,
    SalaryFloorRule,
    SeniorityRule,
    StackRule,
)
from jobhunt.models import Filters, Job, RawPosting


def _job(**fields: object) -> Job:
    raw = RawPosting(
        external_id="x",
        title=str(fields.pop("title", "Senior Python Engineer")),
        company=str(fields.pop("company", "ACME")),
        url="https://x",
        source="test",
        description=fields.pop("description", None),  # type: ignore[arg-type]
        location=fields.pop("location", "Remote"),  # type: ignore[arg-type]
        language=fields.pop("language", "en"),  # type: ignore[arg-type]
        salary_min_eur=fields.pop("salary_min_eur", None),  # type: ignore[arg-type]
        salary_max_eur=fields.pop("salary_max_eur", None),  # type: ignore[arg-type]
    )
    assert not fields, f"unused kwargs: {fields}"
    return Job.from_raw(raw, fetched_at=datetime(2026, 4, 29, tzinfo=UTC))


def _filters() -> Filters:
    return Filters(
        min_salary_eur=90000,
        allowed_locations=["remote", "karlsruhe", "frankfurt", "munich"],
        seniority=["senior", "lead", "staff", "principal"],
        stack_must_haves=["php", "symfony", "python"],
    )


class TestSalaryFloorRule:
    def test_below_floor_rejects(self) -> None:
        rule = SalaryFloorRule()
        result = rule.evaluate(_job(salary_max_eur=70000), _filters())
        assert isinstance(result, Reject)

    def test_at_floor_passes(self) -> None:
        rule = SalaryFloorRule()
        result = rule.evaluate(_job(salary_max_eur=90000), _filters())
        assert isinstance(result, Pass)

    def test_above_floor_passes(self) -> None:
        rule = SalaryFloorRule()
        result = rule.evaluate(_job(salary_max_eur=120000), _filters())
        assert isinstance(result, Pass)

    def test_missing_salary_passes_with_flag(self) -> None:
        rule = SalaryFloorRule()
        result = rule.evaluate(_job(), _filters())
        assert isinstance(result, Pass)
        assert "salary_unstated" in result.flags


class TestLocationAllowlistRule:
    def test_remote_passes(self) -> None:
        rule = LocationAllowlistRule()
        assert isinstance(rule.evaluate(_job(location="Remote"), _filters()), Pass)

    def test_karlsruhe_passes(self) -> None:
        rule = LocationAllowlistRule()
        assert isinstance(rule.evaluate(_job(location="Karlsruhe"), _filters()), Pass)

    def test_unknown_city_rejects(self) -> None:
        rule = LocationAllowlistRule()
        result = rule.evaluate(_job(location="Berlin"), _filters())
        assert isinstance(result, Reject)

    def test_case_insensitive(self) -> None:
        rule = LocationAllowlistRule()
        assert isinstance(rule.evaluate(_job(location="KARLSRUHE"), _filters()), Pass)


class TestLanguageRule:
    def test_english_only_passes(self) -> None:
        rule = LanguageRule()
        assert isinstance(rule.evaluate(_job(language="en"), _filters()), Pass)

    def test_german_only_required_rejects(self) -> None:
        rule = LanguageRule()
        result = rule.evaluate(
            _job(language="de", description="Deutsch C2 Muttersprache erforderlich."),
            _filters(),
        )
        assert isinstance(result, Reject)

    def test_german_with_english_signal_passes(self) -> None:
        rule = LanguageRule()
        result = rule.evaluate(
            _job(language="de", description="Deutsch C2 / English fluent required."),
            _filters(),
        )
        assert isinstance(result, Pass)


class TestSeniorityRule:
    def test_junior_rejects(self) -> None:
        rule = SeniorityRule()
        result = rule.evaluate(_job(title="Junior Python Developer"), _filters())
        assert isinstance(result, Reject)

    def test_intern_rejects(self) -> None:
        rule = SeniorityRule()
        result = rule.evaluate(_job(title="Software Intern"), _filters())
        assert isinstance(result, Reject)

    def test_senior_passes(self) -> None:
        rule = SeniorityRule()
        result = rule.evaluate(_job(title="Senior Python Engineer"), _filters())
        assert isinstance(result, Pass)


class TestStackRule:
    def test_python_in_title_passes(self) -> None:
        rule = StackRule()
        result = rule.evaluate(_job(title="Senior Python Engineer"), _filters())
        assert isinstance(result, Pass)
        assert result.flags == frozenset()

    def test_no_match_passes_with_flag(self) -> None:
        rule = StackRule()
        result = rule.evaluate(
            _job(title="Senior Go Engineer", description="we use Go and Rust"), _filters()
        )
        assert isinstance(result, Pass)
        assert "stack_mismatch" in result.flags
