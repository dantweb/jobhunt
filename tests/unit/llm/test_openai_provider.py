from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from jobhunt.exceptions import LLMResponseError, MissingCredentialsError
from jobhunt.llm.openai_provider import OpenAIProvider
from jobhunt.models import Filters, Job, RawPosting
from tests.unit.llm._fakes import FakeOpenAIClient


def _make_provider(response_text: str) -> tuple[OpenAIProvider, FakeOpenAIClient]:
    fake = FakeOpenAIClient(response_text=response_text)
    provider = OpenAIProvider(
        api_key="test-key",
        model_rank="gpt-4o-mini",
        model_tailor="gpt-4o",
        model_profile="gpt-4o",
        client=fake,
    )
    return provider, fake


def _sample_job() -> Job:
    raw = RawPosting(
        external_id="x",
        title="Senior Python",
        company="ACME",
        url="https://x",
        source="arbeitnow",
        language="en",
    )
    return Job.from_raw(raw, fetched_at=datetime(2026, 4, 29, tzinfo=UTC))


def _filters() -> Filters:
    return Filters(
        min_salary_eur=80000,
        allowed_locations=["remote"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )


def test_missing_api_key_raises() -> None:
    with pytest.raises(MissingCredentialsError):
        OpenAIProvider(
            api_key="",
            model_rank="x",
            model_tailor="y",
            model_profile="z",
        )


def test_rank_parses_response() -> None:
    provider, _ = _make_provider(json.dumps({"score": 65, "reason": "ok", "flags": []}))
    result = provider.rank(_sample_job(), "CV", _filters())
    assert result.score == 65


def test_rank_invalid_json_raises() -> None:
    provider, _ = _make_provider("not json")
    with pytest.raises(LLMResponseError):
        provider.rank(_sample_job(), "CV", _filters())


def test_rank_uses_json_response_format() -> None:
    provider, fake = _make_provider(json.dumps({"score": 50, "reason": "ok"}))
    provider.rank(_sample_job(), "CV", _filters())
    assert fake.calls[-1]["response_format"] == {"type": "json_object"}


def test_tailor_returns_text() -> None:
    provider, fake = _make_provider("Hello,\n\nI am writing to apply...\n")
    letter = provider.tailor(_sample_job(), "CV", "en")
    assert letter.startswith("Hello,")
    # tailor must NOT request JSON-only format.
    assert "response_format" not in fake.calls[-1]


def test_tailor_empty_response_raises() -> None:
    provider, _ = _make_provider("")
    with pytest.raises(LLMResponseError):
        provider.tailor(_sample_job(), "CV", "en")


def test_extract_profile_parses() -> None:
    payload = {
        "min_salary_eur": 100000,
        "allowed_locations": ["eu-remote"],
        "language_preference": "en",
        "language_fallback": "de",
        "seniority": ["staff"],
        "stack_must_haves": ["python"],
    }
    provider, _ = _make_provider(json.dumps(payload))
    draft = provider.extract_profile("CV TEXT")
    assert draft.min_salary_eur == 100000
    assert draft.seniority == ["staff"]
