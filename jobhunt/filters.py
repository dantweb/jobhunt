"""Pluggable hard-filter rules consumed by `Ranker`.

Adding a new rule = adding a `FilterRule` subclass and registering it in
the `Ranker` constructor. No edits to existing rules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from jobhunt.models import Filters, Job


@dataclass(frozen=True)
class Pass:
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Reject:
    reason: str


RuleResult = Pass | Reject


class FilterRule(ABC):
    name: str

    @abstractmethod
    def evaluate(self, job: Job, filters: Filters) -> RuleResult: ...


class SalaryFloorRule(FilterRule):
    name = "salary_floor"

    def evaluate(self, job: Job, filters: Filters) -> RuleResult:
        if job.salary_min_eur is None and job.salary_max_eur is None:
            return Pass(flags=frozenset({"salary_unstated"}))
        upper_bound = job.salary_max_eur or job.salary_min_eur or 0
        if upper_bound < filters.min_salary_eur:
            return Reject(reason=f"salary {upper_bound} below floor {filters.min_salary_eur}")
        return Pass()


class LocationAllowlistRule(FilterRule):
    name = "location_allowlist"

    def evaluate(self, job: Job, filters: Filters) -> RuleResult:
        if not job.location:
            return Pass()
        haystack = job.location.lower()
        for needle in filters.allowed_locations:
            if needle.lower() in haystack:
                return Pass()
        return Reject(reason=f"location {job.location!r} not in allowlist")


class LanguageRule(FilterRule):
    name = "language"

    GERMAN_ONLY_PHRASES = (
        "deutsch c2",
        "muttersprache",
        "verhandlungssicher deutsch",
    )

    def evaluate(self, job: Job, filters: Filters) -> RuleResult:
        description = (job.description or "").lower()
        title_and_desc = f"{job.title.lower()} {description}"
        has_english_signal = (
            job.language and job.language.lower().startswith("en")
        ) or "english" in title_and_desc
        is_german_only = (
            any(phrase in description for phrase in self.GERMAN_ONLY_PHRASES)
            and not has_english_signal
        )
        if is_german_only:
            return Reject(reason="german-only posting")
        return Pass()


class SeniorityRule(FilterRule):
    name = "seniority"

    JUNIOR_TOKENS = ("junior", "praktikant", "intern", "werkstudent", "trainee")

    def evaluate(self, job: Job, filters: Filters) -> RuleResult:
        title = job.title.lower()
        if any(token in title for token in self.JUNIOR_TOKENS):
            return Reject(reason="junior/intern role")
        if any(token in title for token in (s.lower() for s in filters.seniority)):
            return Pass()
        # No explicit seniority signal in the title — keep, mark soft mismatch via flag.
        return Pass(flags=frozenset({"seniority_mismatch"}))


class StackRule(FilterRule):
    name = "stack"

    def evaluate(self, job: Job, filters: Filters) -> RuleResult:
        haystack = f"{job.title.lower()} {(job.description or '').lower()}"
        if any(must.lower() in haystack for must in filters.stack_must_haves):
            return Pass()
        return Pass(flags=frozenset({"stack_mismatch"}))


DEFAULT_RULES: tuple[FilterRule, ...] = (
    SalaryFloorRule(),
    LocationAllowlistRule(),
    LanguageRule(),
    SeniorityRule(),
    StackRule(),
)
