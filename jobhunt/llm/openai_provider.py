from __future__ import annotations

from typing import Any, Literal

import openai

from jobhunt.exceptions import LLMResponseError, MissingCredentialsError
from jobhunt.llm._parsing import parse_profile_json, parse_rank_json
from jobhunt.llm.base import LLMProvider
from jobhunt.models import Filters, Job, ProfileDraft, RankResult
from jobhunt.prompts import profile as profile_prompt
from jobhunt.prompts import rank as rank_prompt
from jobhunt.prompts import tailor as tailor_prompt


class OpenAIProvider(LLMProvider):
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
            raise MissingCredentialsError("openai", missing=["api_key"])
        self._client = client if client is not None else openai.OpenAI(api_key=api_key)
        self._model_rank = model_rank
        self._model_tailor = model_tailor
        self._model_profile = model_profile

    def rank(self, job: Job, cv: str, filters: Filters) -> RankResult:
        text = self._call(
            model=self._model_rank,
            system=rank_prompt.SYSTEM,
            user=rank_prompt.user_prompt(job, cv, filters),
            json_only=True,
            max_tokens=512,
        )
        return parse_rank_json(text)

    def tailor(self, job: Job, cv: str, language: Literal["en", "de"]) -> str:
        text = self._call(
            model=self._model_tailor,
            system=tailor_prompt.system_prompt(language),
            user=tailor_prompt.user_prompt(job, cv, language),
            json_only=False,
            max_tokens=1500,
        )
        if not text.strip():
            raise LLMResponseError("empty cover letter from openai")
        return text.strip()

    def extract_profile(self, cv_text: str) -> ProfileDraft:
        text = self._call(
            model=self._model_profile,
            system=profile_prompt.SYSTEM,
            user=profile_prompt.user_prompt(cv_text),
            json_only=True,
            max_tokens=512,
        )
        return parse_profile_json(text)

    def _call(
        self,
        *,
        model: str,
        system: str,
        user: str,
        json_only: bool,
        max_tokens: int,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_only:
            kwargs["response_format"] = {"type": "json_object"}
        completion = self._client.chat.completions.create(**kwargs)
        return _extract_text(completion)


def _extract_text(completion: Any) -> str:
    choices = getattr(completion, "choices", None)
    if not choices:
        raise LLMResponseError("openai completion has no choices")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if not isinstance(content, str):
        raise LLMResponseError("openai completion has no string content")
    return content
