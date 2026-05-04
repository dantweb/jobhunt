from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from jobhunt.exceptions import LLMResponseError, MissingCredentialsError
from jobhunt.llm.anthropic_provider import AnthropicProvider
from jobhunt.models import Filters, Job, RawPosting
from tests.unit.llm._fakes import FakeAnthropicClient


def _make_provider(response_text: str) -> tuple[AnthropicProvider, FakeAnthropicClient]:
    fake = FakeAnthropicClient(response_text=response_text)
    provider = AnthropicProvider(
        api_key="test-key",
        model_rank="claude-haiku-4-5",
        model_tailor="claude-sonnet-4-6",
        model_profile="claude-sonnet-4-6",
        client=fake,
    )
    return provider, fake


def _sample_job() -> Job:
    raw = RawPosting(
        external_id="x",
        title="Senior Python Engineer",
        company="ACME",
        url="https://x",
        source="bundesagentur",
        location="Berlin",
        language="en",
    )
    return Job.from_raw(raw, fetched_at=datetime(2026, 4, 29, tzinfo=UTC))


def _sample_filters() -> Filters:
    return Filters(
        min_salary_eur=90000,
        allowed_locations=["remote", "berlin"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )


def test_missing_api_key_raises() -> None:
    with pytest.raises(MissingCredentialsError):
        AnthropicProvider(
            api_key="",
            model_rank="x",
            model_tailor="y",
            model_profile="z",
        )


def test_rank_parses_json_response() -> None:
    provider, _ = _make_provider(
        json.dumps({"score": 78, "reason": "strong python match", "flags": ["salary_unstated"]})
    )
    result = provider.rank(_sample_job(), "CV TEXT", _sample_filters())
    assert result.score == 78
    assert "python" in result.reason
    assert "salary_unstated" in result.flags


def test_rank_invalid_json_raises_llm_response_error() -> None:
    provider, _ = _make_provider("not json")
    with pytest.raises(LLMResponseError):
        provider.rank(_sample_job(), "CV", _sample_filters())


def test_rank_score_out_of_range_raises() -> None:
    provider, _ = _make_provider(json.dumps({"score": 150, "reason": "x"}))
    with pytest.raises(LLMResponseError):
        provider.rank(_sample_job(), "CV", _sample_filters())


def test_tailor_returns_text() -> None:
    provider, fake = _make_provider("Sehr geehrte Damen und Herren,\n\n…")
    letter = provider.tailor(_sample_job(), "CV", "de")
    assert letter.startswith("Sehr geehrte")
    assert fake.calls[-1]["model"] == "claude-sonnet-4-6"


def test_tailor_empty_response_raises() -> None:
    provider, _ = _make_provider("   \n\n  ")
    with pytest.raises(LLMResponseError):
        provider.tailor(_sample_job(), "CV", "en")


def test_extract_profile_parses_response() -> None:
    payload = {
        "min_salary_eur": 95000,
        "allowed_locations": ["remote", "karlsruhe"],
        "language_preference": "en",
        "language_fallback": "de",
        "seniority": ["senior", "lead"],
        "stack_must_haves": ["python", "php"],
    }
    provider, _ = _make_provider(json.dumps(payload))
    draft = provider.extract_profile("CV TEXT")
    assert draft.min_salary_eur == 95000
    assert draft.allowed_locations == ["remote", "karlsruhe"]


def test_cv_block_marked_for_prompt_caching() -> None:
    provider, fake = _make_provider(json.dumps({"score": 50, "reason": "ok"}))
    provider.rank(_sample_job(), "MY CV CONTENT", _sample_filters())
    request = fake.calls[-1]
    system_blocks = request["system"]
    cv_block = system_blocks[-1]
    assert "MY CV CONTENT" in cv_block["text"]
    assert cv_block["cache_control"] == {"type": "ephemeral"}
