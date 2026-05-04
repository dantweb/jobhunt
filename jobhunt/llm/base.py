from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from jobhunt.models import Filters, Job, ProfileDraft, RankResult


class LLMProvider(ABC):
    """A pluggable LLM provider.

    Three methods. Each is a Liskov-substitutable boundary, contract-tested.
    """

    @abstractmethod
    def rank(self, job: Job, cv: str, filters: Filters) -> RankResult: ...

    @abstractmethod
    def tailor(self, job: Job, cv: str, language: Literal["en", "de"]) -> str: ...

    @abstractmethod
    def extract_profile(self, cv_text: str) -> ProfileDraft: ...
