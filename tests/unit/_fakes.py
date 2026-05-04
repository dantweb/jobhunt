"""Shared in-process fakes for tests across sub-sprints 05-07."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fpdf import FPDF

from jobhunt.cv.reader import CvReader
from jobhunt.llm.base import LLMProvider
from jobhunt.models import Filters, Job, ProfileDraft, RankResult, RawPosting
from jobhunt.sources.base import JobSource


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        rank_result: RankResult | None = None,
        cover_letter: str = "Dear hiring team,\n\nI am applying...",
        profile: ProfileDraft | None = None,
    ) -> None:
        self._rank_result = rank_result or RankResult(score=70, reason="fake")
        self._cover_letter = cover_letter
        self._profile = profile or ProfileDraft(
            min_salary_eur=80000,
            allowed_locations=["remote"],
            seniority=["senior"],
            stack_must_haves=["python"],
        )
        self.rank_calls: list[tuple[Job, str, Filters]] = []
        self.tailor_calls: list[tuple[Job, str, Literal["en", "de"]]] = []
        self.profile_calls: list[str] = []

    def rank(self, job: Job, cv: str, filters: Filters) -> RankResult:
        self.rank_calls.append((job, cv, filters))
        return self._rank_result

    def tailor(self, job: Job, cv: str, language: Literal["en", "de"]) -> str:
        self.tailor_calls.append((job, cv, language))
        return self._cover_letter

    def extract_profile(self, cv_text: str) -> ProfileDraft:
        self.profile_calls.append(cv_text)
        return self._profile


class FakeJobSource(JobSource):
    def __init__(
        self,
        postings: list[RawPosting],
        *,
        raises: Exception | None = None,
        name: str = "fake",
    ) -> None:
        self.name = name
        self._postings = postings
        self._raises = raises
        self.fetch_calls: int = 0

    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        self.fetch_calls += 1
        if self._raises is not None:
            raise self._raises
        return list(self._postings)


class FakeCvReader(CvReader):
    def __init__(self, text: str = "FAKE CV TEXT") -> None:
        self._text = text
        self.calls: list[Path] = []

    def read(self, path: Path) -> str:
        self.calls.append(path)
        return self._text


def write_minimal_pdf(path: Path, text: str = "Test Candidate - Senior Backend Engineer") -> Path:
    """Generate a synthetic single-page PDF fixture."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.splitlines() or [text]:
        pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))
    return path


def make_raw(
    *,
    idx: int,
    title: str = "Senior Python Engineer",
    company: str | None = None,
    location: str | None = "Remote",
    description: str | None = None,
    salary_min_eur: int | None = None,
    salary_max_eur: int | None = None,
    language: str | None = "en",
    source: str = "fake",
    contact_email: str | None = None,
    apply_url: str | None = None,
    **extra: Any,
) -> RawPosting:
    return RawPosting(
        external_id=f"ext-{idx}",
        title=title,
        company=company or f"Company-{idx}",
        url=f"https://example.com/jobs/{idx}",
        source=source,
        description=description,
        location=location,
        language=language,
        salary_min_eur=salary_min_eur,
        salary_max_eur=salary_max_eur,
        contact_email=contact_email,
        apply_url=apply_url,
        **extra,
    )
