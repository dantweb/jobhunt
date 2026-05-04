"""Prompt templates for `LLMProvider.rank()`."""

from __future__ import annotations

from jobhunt.models import Filters, Job

SYSTEM = (
    "You are a hiring-fit ranker. You score job postings against a candidate's CV "
    "and the candidate's hard-filter preferences. You always respond with strict JSON "
    'matching the schema: {"score": int 0-100, "reason": string, "flags": [string]}. '
    "Allowed flags: salary_unstated, german_only, seniority_mismatch, stack_mismatch, "
    "location_mismatch, language_mismatch."
)


def user_prompt(job: Job, cv: str, filters: Filters) -> str:
    return (
        "Rank this posting for the candidate.\n\n"
        f"Filters:\n"
        f"- min_salary_eur: {filters.min_salary_eur}\n"
        f"- allowed_locations: {', '.join(filters.allowed_locations)}\n"
        f"- language_preference: {filters.language_preference}\n"
        f"- seniority: {', '.join(filters.seniority)}\n"
        f"- stack_must_haves: {', '.join(filters.stack_must_haves)}\n\n"
        f"Posting:\n"
        f"- title: {job.title}\n"
        f"- company: {job.company}\n"
        f"- location: {job.location or 'unknown'}\n"
        f"- language: {job.language or 'unknown'}\n"
        f"- salary: {job.salary_min_eur or '?'} - {job.salary_max_eur or '?'} EUR\n"
        f"- description: {job.description or ''}\n\n"
        f"CV:\n{cv}\n\n"
        "Respond with the JSON only."
    )
