from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from typing import ClassVar

from jobhunt.models import RawPosting


class JobSource(ABC):
    """A source of job postings.

    Subclasses speak only their source's HTTP API. They do not touch the
    DB, do not score, do not dedupe.
    """

    name: ClassVar[str]

    @abstractmethod
    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        """Yield postings. Each `RawPosting` must have all required fields populated."""
