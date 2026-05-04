"""Shared response parsers for both LLM providers.

LLMs frequently wrap JSON in a ```json … ``` fence even when asked not to.
We strip the fence before parsing so the contract that the provider returns
parsed Python objects holds regardless of which fence-style the model
happened to emit on a given call.
"""

from __future__ import annotations

import json
import re

from jobhunt.exceptions import LLMResponseError
from jobhunt.models import ProfileDraft, RankResult

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def strip_code_fence(text: str) -> str:
    match = _FENCE_RE.match(text)
    if match:
        return match.group(1)
    return text.strip()


def parse_rank_json(text: str) -> RankResult:
    payload = strip_code_fence(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"rank response is not JSON: {text!r}") from exc
    try:
        return RankResult(
            score=int(data["score"]),
            reason=str(data["reason"]),
            flags=frozenset(data.get("flags") or []),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise LLMResponseError(f"rank response failed validation: {data!r}") from exc


def parse_profile_json(text: str) -> ProfileDraft:
    payload = strip_code_fence(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"profile response is not JSON: {text!r}") from exc
    return ProfileDraft.model_validate(data)
