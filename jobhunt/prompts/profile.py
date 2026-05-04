"""Prompt template for `LLMProvider.extract_profile()`."""

from __future__ import annotations

SYSTEM = (
    "You read a CV and return a hiring-filter profile as strict JSON matching: "
    '{"min_salary_eur": int, "allowed_locations": [string], '
    '"language_preference": "en" or "de", "language_fallback": "en" or "de", '
    '"seniority": [string], "stack_must_haves": [string]}. '
    'Defaults when the CV is silent: min_salary_eur=0, allowed_locations=["remote"], '
    'language_preference="en", language_fallback="de", seniority=["senior"], '
    "stack_must_haves=[]."
)


def user_prompt(cv_text: str) -> str:
    return f"Extract the profile from this CV:\n\n{cv_text}\n\nReturn the JSON only."
