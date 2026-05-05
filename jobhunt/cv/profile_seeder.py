from __future__ import annotations

from pathlib import Path

from jobhunt.cv.reader import CvReader
from jobhunt.llm.base import LLMProvider
from jobhunt.models import ProfileDraft


class ProfileSeeder:
    def __init__(self, *, llm: LLMProvider, reader: CvReader) -> None:
        self._llm = llm
        self._reader = reader

    def seed(self, cv_path: Path) -> ProfileDraft:
        cv_text = self._reader.read(cv_path)
        return self._llm.extract_profile(cv_text)
