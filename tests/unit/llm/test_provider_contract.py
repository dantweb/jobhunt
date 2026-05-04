"""Liskov contract test for LLMProvider — runs against every implementation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from jobhunt.llm import AnthropicProvider, LLMProvider, OpenAIProvider
from jobhunt.models import Filters, Job, ProfileDraft, RankResult, RawPosting
from tests.unit.llm._fakes import FakeAnthropicClient, FakeOpenAIClient


def _job() -> Job:
    raw = RawPosting(
        external_id="x",
        title="Senior Python Engineer",
        company="ACME",
        url="https://x",
        source="contract-test",
    )
    return Job.from_raw(raw, fetched_at=datetime(2026, 4, 29, tzinfo=UTC))


def _filters() -> Filters:
    return Filters(
        min_salary_eur=80000,
        allowed_locations=["remote"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )


def _make_anthropic(response_text: str) -> LLMProvider:
    return AnthropicProvider(
        api_key="test",
        model_rank="claude-haiku-4-5",
        model_tailor="claude-sonnet-4-6",
        model_profile="claude-sonnet-4-6",
        client=FakeAnthropicClient(response_text=response_text),
    )


def _make_openai(response_text: str) -> LLMProvider:
    return OpenAIProvider(
        api_key="test",
        model_rank="gpt-4o-mini",
        model_tailor="gpt-4o",
        model_profile="gpt-4o",
        client=FakeOpenAIClient(response_text=response_text),
    )


PROVIDER_FACTORIES: list[Callable[[str], LLMProvider]] = [_make_anthropic, _make_openai]


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES)
def test_rank_returns_valid_result(factory: Callable[[str], LLMProvider]) -> None:
    provider = factory(json.dumps({"score": 80, "reason": "strong python match", "flags": []}))
    result = provider.rank(_job(), "CV TEXT", _filters())
    assert isinstance(result, RankResult)
    assert 0 <= result.score <= 100
    assert result.reason


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES)
def test_tailor_returns_non_empty_text(factory: Callable[[str], LLMProvider]) -> None:
    provider = factory("Sehr geehrte Damen und Herren,\nIch bewerbe mich…")
    letter = provider.tailor(_job(), "CV", "de")
    assert isinstance(letter, str)
    assert letter.strip()


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES)
def test_tailor_language_param_authoritative(factory: Callable[[str], LLMProvider]) -> None:
    """Provider does NOT decide language — caller does. Both `en` and `de`
    must be accepted and routed to the matching template."""
    en_provider = factory("Hello,\nThanks.")
    de_provider = factory("Sehr geehrte,\nDanke.")
    assert en_provider.tailor(_job(), "CV", "en").lower().startswith("hello")
    assert "geehrte" in de_provider.tailor(_job(), "CV", "de").lower()


@pytest.mark.parametrize("factory", PROVIDER_FACTORIES)
def test_extract_profile_returns_profile_draft(factory: Callable[[str], LLMProvider]) -> None:
    payload = {
        "min_salary_eur": 90000,
        "allowed_locations": ["remote"],
        "language_preference": "en",
        "language_fallback": "de",
        "seniority": ["senior"],
        "stack_must_haves": ["python"],
    }
    provider = factory(json.dumps(payload))
    draft = provider.extract_profile("CV TEXT")
    assert isinstance(draft, ProfileDraft)
    assert draft.min_salary_eur == 90000
    assert draft.allowed_locations == ["remote"]
    # Round-trip: ProfileDraft → Filters works for any provider's output.
    filters = draft.to_filters()
    assert filters.min_salary_eur == 90000
