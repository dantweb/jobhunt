from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from jobhunt.models import Job, RawPosting
from jobhunt.ranker import Ranker
from jobhunt.repositories import JobRepository
from jobhunt.sources.base import JobSource


@dataclass
class FetchReport:
    fetched_per_source: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    saved: int = 0
    scored: int = 0
    shortlisted: int = 0


class FetchService:
    def __init__(
        self,
        *,
        sources: Sequence[JobSource],
        jobs: JobRepository,
        ranker: Ranker,
        shortlist_size: int,
    ) -> None:
        self._sources = tuple(sources)
        self._jobs = jobs
        self._ranker = ranker
        self._shortlist_size = shortlist_size

    def run(self) -> FetchReport:
        report = FetchReport()
        all_postings: list[RawPosting] = []
        for source in self._sources:
            try:
                postings = list(source.fetch())
            except Exception as exc:
                report.failures[source.name] = repr(exc)
                continue
            report.fetched_per_source[source.name] = len(postings)
            all_postings.extend(postings)

        now = datetime.now(tz=UTC)
        new_jobs: list[Job] = [Job.from_raw(p, fetched_at=now) for p in all_postings]
        report.saved = self._jobs.save_many(new_jobs)

        unscored = self._jobs.unscored()
        scored_pairs = self._ranker.score_many(unscored)
        for job, result in scored_pairs:
            self._jobs.update_score(job.id, result)
        report.scored = len(scored_pairs)

        ranked = sorted(scored_pairs, key=lambda pair: pair[1].score, reverse=True)
        top = [pair[0].id for pair in ranked[: self._shortlist_size]]
        if top:
            self._jobs.mark_shortlisted(top)
        report.shortlisted = len(top)
        return report
