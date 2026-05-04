from __future__ import annotations

from datetime import UTC, datetime

from jobhunt.models import Job, RawPosting
from jobhunt.tailor import Tailor
from tests.unit._fakes import FakeLLMProvider


def _job(language: str | None) -> Job:
    raw = RawPosting(
        external_id="x",
        title="Senior Python",
        company="ACME",
        url="https://x",
        source="test",
        language=language,
    )
    return Job.from_raw(raw, fetched_at=datetime(2026, 4, 29, tzinfo=UTC))


def test_english_posting_yields_english_call() -> None:
    llm = FakeLLMProvider()
    tailor = Tailor(llm=llm, cv="CV", owner_preference="en")
    tailor.write(_job(language="en"))
    assert llm.tailor_calls[-1][2] == "en"


def test_german_posting_yields_german_call() -> None:
    llm = FakeLLMProvider()
    tailor = Tailor(llm=llm, cv="CV", owner_preference="en")
    tailor.write(_job(language="de"))
    assert llm.tailor_calls[-1][2] == "de"


def test_mixed_or_unknown_uses_owner_preference() -> None:
    llm = FakeLLMProvider()
    tailor = Tailor(llm=llm, cv="CV", owner_preference="en")
    tailor.write(_job(language=None))
    tailor.write(_job(language="other"))
    assert all(call[2] == "en" for call in llm.tailor_calls)
