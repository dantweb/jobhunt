"""Domain models — the canonical shapes the rest of the codebase pivots on."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_FLAGS: frozenset[str] = frozenset(
    {
        "salary_unstated",
        "german_only",
        "seniority_mismatch",
        "stack_mismatch",
        "location_mismatch",
        "language_mismatch",
    }
)


class Decision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class Delivery(StrEnum):
    EMAIL = "email"
    BROWSER = "browser"


def _normalise(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class RawPosting(BaseModel):
    """What a `JobSource.fetch()` returns. One row per posting per source."""

    model_config = ConfigDict(frozen=True)

    external_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    url: str = Field(min_length=1)
    source: str = Field(min_length=1)
    description: str | None = None
    salary_min_eur: int | None = None
    salary_max_eur: int | None = None
    location: str | None = None
    language: str | None = None
    posted_at: datetime | None = None
    contact_email: str | None = None
    apply_url: str | None = None


class Job(BaseModel):
    """Canonical normalised posting. `id` is the dedupe hash."""

    model_config = ConfigDict(frozen=True)

    id: str
    external_id: str
    source: str
    title: str
    company: str
    url: str
    description: str | None = None
    salary_min_eur: int | None = None
    salary_max_eur: int | None = None
    location: str | None = None
    language: str | None = None
    posted_at: datetime | None = None
    contact_email: str | None = None
    apply_url: str | None = None
    fetched_at: datetime
    score: int | None = None
    score_reason: str | None = None
    score_flags: frozenset[str] = frozenset()
    shortlisted: bool = False

    @staticmethod
    def dedupe_hash(*, title: str, company: str, location: str | None) -> str:
        canonical = "|".join([_normalise(title), _normalise(company), _normalise(location or "")])
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_raw(cls, raw: RawPosting, *, fetched_at: datetime | None = None) -> Job:
        return cls(
            id=cls.dedupe_hash(title=raw.title, company=raw.company, location=raw.location),
            external_id=raw.external_id,
            source=raw.source,
            title=raw.title,
            company=raw.company,
            url=raw.url,
            description=raw.description,
            salary_min_eur=raw.salary_min_eur,
            salary_max_eur=raw.salary_max_eur,
            location=raw.location,
            language=raw.language,
            posted_at=raw.posted_at,
            contact_email=raw.contact_email,
            apply_url=raw.apply_url,
            fetched_at=fetched_at or _utcnow(),
        )


class Application(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str
    decision: Decision = Decision.PENDING
    cover_letter: str | None = None
    sent_at: datetime | None = None
    delivery: Delivery | None = None
    notes: str | None = None


class RankResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1)
    flags: frozenset[str] = frozenset()

    @field_validator("flags", mode="before")
    @classmethod
    def _coerce_flags(cls, value: object) -> frozenset[str]:
        if value is None:
            return frozenset()
        if isinstance(value, str):
            return frozenset({value})
        if isinstance(value, (list, tuple, set, frozenset)):
            return frozenset(str(f) for f in value)
        raise TypeError(f"flags must be iterable[str], got {type(value).__name__}")

    @field_validator("flags")
    @classmethod
    def _flags_in_allowed_set(cls, value: frozenset[str]) -> frozenset[str]:
        unknown = value - ALLOWED_FLAGS
        if unknown:
            raise ValueError(f"unknown flags: {sorted(unknown)}")
        return value


class Filters(BaseModel):
    """Hard-filter policy. Single source of truth — `Ranker` reads this."""

    model_config = ConfigDict(frozen=True)

    min_salary_eur: int = Field(ge=0)
    allowed_locations: list[str] = Field(min_length=1)
    language_preference: Literal["en", "de"] = "en"
    language_fallback: Literal["en", "de"] = "de"
    seniority: list[str] = Field(min_length=1)
    stack_must_haves: list[str] = Field(min_length=1)
    shortlist_size: int = Field(default=20, ge=1)


class ProfileDraft(BaseModel):
    """Output of `LLMProvider.extract_profile()`. Same shape as `Filters`
    but every field has a sensible default for when the CV is silent.
    """

    model_config = ConfigDict(frozen=True)

    min_salary_eur: int = 0
    allowed_locations: list[str] = Field(default_factory=lambda: ["remote"])
    language_preference: Literal["en", "de"] = "en"
    language_fallback: Literal["en", "de"] = "de"
    seniority: list[str] = Field(default_factory=lambda: ["senior"])
    stack_must_haves: list[str] = Field(default_factory=list)
    shortlist_size: int = 20

    def to_filters(self) -> Filters:
        return Filters.model_validate(self.model_dump())
