from __future__ import annotations

import json

import pytest

from jobhunt.exceptions import LLMResponseError
from jobhunt.llm._parsing import parse_profile_json, parse_rank_json, strip_code_fence


class TestStripCodeFence:
    def test_passes_plain_json_through(self) -> None:
        assert strip_code_fence('{"a": 1}') == '{"a": 1}'

    def test_strips_json_fence(self) -> None:
        wrapped = '```json\n{"a": 1}\n```'
        assert strip_code_fence(wrapped) == '{"a": 1}'

    def test_strips_bare_fence(self) -> None:
        wrapped = '```\n{"a": 1}\n```'
        assert strip_code_fence(wrapped) == '{"a": 1}'

    def test_strips_surrounding_whitespace(self) -> None:
        assert strip_code_fence('   {"a": 1}\n  ') == '{"a": 1}'

    def test_case_insensitive_language_tag(self) -> None:
        assert strip_code_fence("```JSON\n{}\n```") == "{}"


class TestParseRankJson:
    def test_plain(self) -> None:
        result = parse_rank_json(json.dumps({"score": 80, "reason": "ok"}))
        assert result.score == 80

    def test_fenced(self) -> None:
        result = parse_rank_json('```json\n{"score": 70, "reason": "fenced"}\n```')
        assert result.score == 70
        assert result.reason == "fenced"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(LLMResponseError):
            parse_rank_json("not json at all")


class TestParseProfileJson:
    def test_fenced_response_from_anthropic(self) -> None:
        # Mirrors the actual fenced response observed from Claude when seeded.
        text = (
            '```json\n{"min_salary_eur": 0, "allowed_locations": ["remote"], '
            '"language_preference": "en", "language_fallback": "de", '
            '"seniority": ["senior", "lead"], '
            '"stack_must_haves": ["PHP8", "Symfony", "Docker", "CI/CD", "e-commerce"]}\n```'
        )
        draft = parse_profile_json(text)
        assert draft.min_salary_eur == 0
        assert draft.allowed_locations == ["remote"]
        assert "Symfony" in draft.stack_must_haves

    def test_plain_response(self) -> None:
        draft = parse_profile_json(
            json.dumps(
                {
                    "min_salary_eur": 95000,
                    "allowed_locations": ["remote"],
                    "language_preference": "en",
                    "language_fallback": "de",
                    "seniority": ["senior"],
                    "stack_must_haves": ["python"],
                }
            )
        )
        assert draft.min_salary_eur == 95000
