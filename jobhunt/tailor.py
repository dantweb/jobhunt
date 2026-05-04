"""Cover-letter generation. Picks language from posting; calls `LLMProvider.tailor`."""

from __future__ import annotations

from typing import Literal

from jobhunt.llm.base import LLMProvider
from jobhunt.models import Job

Language = Literal["en", "de"]


class Tailor:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        cv: str,
        owner_preference: Language = "en",
    ) -> None:
        self._llm = llm
        self._cv = cv
        self._owner_preference = owner_preference

    def write(self, job: Job) -> str:
        language = self._pick_language(job)
        return self._llm.tailor(job, self._cv, language)

    def _pick_language(self, job: Job) -> Language:
        explicit = (job.language or "").lower()
        if explicit.startswith("en"):
            return "en"
        if explicit.startswith("de"):
            return "de"
        # Mixed or unknown → owner preference.
        return self._owner_preference
