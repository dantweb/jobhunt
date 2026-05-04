"""Cover-letter prompt templates."""

from __future__ import annotations

from typing import Literal

from jobhunt.models import Job

SYSTEM_EN = (
    "You write concise, specific cover letters in English. "
    "Hello/regards salutations only. No emojis. 250-350 words."
)

SYSTEM_DE = (
    "Du schreibst prägnante, spezifische Anschreiben auf Deutsch in 'Sie'-Form. "
    "Förmliche Anrede ('Sehr geehrte Damen und Herren'). Keine Emojis. 250-350 Wörter."
)


def system_prompt(language: Literal["en", "de"]) -> str:
    return SYSTEM_EN if language == "en" else SYSTEM_DE


def user_prompt(job: Job, cv: str, language: Literal["en", "de"]) -> str:
    if language == "en":
        return (
            f"Write a cover letter for this role.\n\n"
            f"Role: {job.title} at {job.company} ({job.location or 'remote'}).\n"
            f"Posting:\n{job.description or ''}\n\n"
            f"Candidate CV:\n{cv}\n\n"
            "Output the letter only — no preamble."
        )
    return (
        f"Schreibe ein Anschreiben für diese Stelle.\n\n"
        f"Stelle: {job.title} bei {job.company} ({job.location or 'remote'}).\n"
        f"Ausschreibung:\n{job.description or ''}\n\n"
        f"Lebenslauf:\n{cv}\n\n"
        "Gib nur das Anschreiben aus — keine Vorrede."
    )
