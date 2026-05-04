from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from jobhunt.models import Application, Decision, Job
from jobhunt.repositories import ApplicationRepository, JobRepository
from jobhunt.tailor import Tailor


@dataclass(frozen=True)
class ReviewItem:
    job: Job


class ReviewService:
    def __init__(
        self,
        *,
        jobs: JobRepository,
        applications: ApplicationRepository,
        tailor: Tailor,
    ) -> None:
        self._jobs = jobs
        self._applications = applications
        self._tailor = tailor

    def next(self) -> Iterator[ReviewItem]:
        for job in self._jobs.shortlisted():
            existing = self._applications.get(job.id)
            if existing is not None and existing.decision != Decision.PENDING:
                continue
            yield ReviewItem(job=job)

    def record(self, *, job_id: str, decision: Decision, notes: str | None = None) -> None:
        cover_letter: str | None = None
        if decision == Decision.APPROVED:
            job = self._jobs.get(job_id)
            cover_letter = self._tailor.write(job)
        self._applications.record_decision(
            Application(
                job_id=job_id,
                decision=decision,
                cover_letter=cover_letter,
                notes=notes,
            )
        )
