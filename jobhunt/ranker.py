"""Hard-filter + LLM scoring orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from jobhunt.filters import DEFAULT_RULES, FilterRule, Reject
from jobhunt.llm.base import LLMProvider
from jobhunt.models import Filters, Job, RankResult


class Ranker:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        filters: Filters,
        cv: str,
        rules: Sequence[FilterRule] = DEFAULT_RULES,
    ) -> None:
        self._llm = llm
        self._filters = filters
        self._cv = cv
        self._rules = tuple(rules)

    def score(self, job: Job) -> RankResult | None:
        accumulated_flags: frozenset[str] = frozenset()
        for rule in self._rules:
            result = rule.evaluate(job, self._filters)
            if isinstance(result, Reject):
                return None
            accumulated_flags = accumulated_flags | result.flags
        llm_result = self._llm.rank(job, self._cv, self._filters)
        return RankResult(
            score=llm_result.score,
            reason=llm_result.reason,
            flags=llm_result.flags | accumulated_flags,
        )

    def score_many(self, jobs: Iterable[Job]) -> list[tuple[Job, RankResult]]:
        results: list[tuple[Job, RankResult]] = []
        for job in jobs:
            result = self.score(job)
            if result is not None:
                results.append((job, result))
        return results
