from __future__ import annotations

from typing import Any, Literal, cast

import anthropic

from jobhunt.exceptions import LLMResponseError, MissingCredentialsError
from jobhunt.llm._parsing import parse_profile_json, parse_rank_json
from jobhunt.llm.base import LLMProvider
from jobhunt.models import Filters, Job, ProfileDraft, RankResult
from jobhunt.prompts import profile as profile_prompt
from jobhunt.prompts import rank as rank_prompt
from jobhunt.prompts import tailor as tailor_prompt


class AnthropicProvider(LLMProvider):
    """Claude implementation. Uses prompt caching on the CV block."""

    def __init__(
        self,
        *,
        api_key: str,
        model_rank: str,
        model_tailor: str,
        model_profile: str,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise MissingCredentialsError("anthropic", missing=["api_key"])
        self._client = client if client is not None else anthropic.Anthropic(api_key=api_key)
        self._model_rank = model_rank
        self._model_tailor = model_tailor
        self._model_profile = model_profile

    def rank(self, job: Job, cv: str, filters: Filters) -> RankResult:
        text = self._call(
            model=self._model_rank,
            system_blocks=[{"type": "text", "text": rank_prompt.SYSTEM}],
            user_text=rank_prompt.user_prompt(job, cv, filters),
            cv_for_cache=cv,
            max_tokens=512,
        )
        return parse_rank_json(text)

    def tailor(self, job: Job, cv: str, language: Literal["en", "de"]) -> str:
        text = self._call(
            model=self._model_tailor,
            system_blocks=[{"type": "text", "text": tailor_prompt.system_prompt(language)}],
            user_text=tailor_prompt.user_prompt(job, cv, language),
            cv_for_cache=cv,
            max_tokens=1500,
        )
        if not text.strip():
            raise LLMResponseError("empty cover letter from anthropic")
        return text.strip()

    def extract_profile(self, cv_text: str) -> ProfileDraft:
        text = self._call(
            model=self._model_profile,
            system_blocks=[{"type": "text", "text": profile_prompt.SYSTEM}],
            user_text=profile_prompt.user_prompt(cv_text),
            cv_for_cache=cv_text,
            max_tokens=512,
        )
        return parse_profile_json(text)

    def _call(
        self,
        *,
        model: str,
        system_blocks: list[dict[str, Any]],
        user_text: str,
        cv_for_cache: str,
        max_tokens: int,
    ) -> str:
        system_with_cache = [
            *system_blocks,
            {
                "type": "text",
                "text": f"Reference CV (do not echo back):\n{cv_for_cache}",
                "cache_control": {"type": "ephemeral"},
            },
        ]
        message = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=cast(Any, system_with_cache),
            messages=[{"role": "user", "content": user_text}],
        )
        return _extract_text(message)


def _extract_text(message: Any) -> str:
    blocks = getattr(message, "content", None)
    if not blocks:
        raise LLMResponseError("anthropic message has no content blocks")
    for block in blocks:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text
    raise LLMResponseError("anthropic message has no text block")
