"""Inspect runtime config and report what's set vs. missing.

Used by `jobhunt init` to give the user concrete next steps after the
seeded `config.toml` is written, instead of a generic "edit .env" hint.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jobhunt.config import AppConfig


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class StatusEntry:
    status: Status
    label: str
    detail: str


def env_status(cfg: AppConfig) -> list[StatusEntry]:
    entries: list[StatusEntry] = []
    entries.append(_llm_entry(cfg))
    entries.extend(_source_entries(cfg))
    entries.append(_smtp_entry(cfg))
    entries.append(_owner_entry(cfg))
    return entries


def _llm_entry(cfg: AppConfig) -> StatusEntry:
    if cfg.LLM_PROVIDER == "anthropic":
        if not cfg.ANTHROPIC_API_KEY:
            return StatusEntry(
                Status.ERROR,
                "Anthropic API key",
                "ANTHROPIC_API_KEY is empty — `jobhunt fetch/review/send` will fail. "
                "See README → Getting API keys → Anthropic Claude.",
            )
        return StatusEntry(Status.OK, "Anthropic API key", "set")
    if not cfg.OPENAI_API_KEY:
        return StatusEntry(
            Status.ERROR,
            "OpenAI API key",
            "OPENAI_API_KEY is empty — `jobhunt fetch/review/send` will fail. "
            "See README → Getting API keys → OpenAI.",
        )
    return StatusEntry(Status.OK, "OpenAI API key", "set")


def _source_entries(cfg: AppConfig) -> list[StatusEntry]:
    entries: list[StatusEntry] = []
    if cfg.ADZUNA_APP_ID and cfg.ADZUNA_APP_KEY:
        entries.append(StatusEntry(Status.OK, "Adzuna", "credentials set"))
    else:
        entries.append(
            StatusEntry(
                Status.WARN,
                "Adzuna",
                "no ADZUNA_APP_ID / ADZUNA_APP_KEY — source will be skipped at fetch time.",
            )
        )
    if cfg.JOOBLE_API_KEY:
        entries.append(StatusEntry(Status.OK, "Jooble", "credentials set"))
    else:
        entries.append(
            StatusEntry(
                Status.WARN,
                "Jooble",
                "no JOOBLE_API_KEY — source will be skipped at fetch time.",
            )
        )
    return entries


def _smtp_entry(cfg: AppConfig) -> StatusEntry:
    if not cfg.SMTP_HOST:
        return StatusEntry(
            Status.ERROR,
            "SMTP",
            "SMTP_HOST is empty — `jobhunt send` will fail. "
            "Default in .env.example is `mailpit` — run `docker compose up -d mailpit`.",
        )
    if cfg.SMTP_HOST == "mailpit":
        return StatusEntry(
            Status.OK,
            "SMTP",
            "mailpit:1025 — captured emails at http://localhost:8125 "
            "(run `docker compose up -d mailpit` if not already running).",
        )
    return StatusEntry(
        Status.OK,
        "SMTP",
        f"{cfg.SMTP_HOST}:{cfg.SMTP_PORT} (real SMTP — emails will be delivered).",
    )


def _owner_entry(cfg: AppConfig) -> StatusEntry:
    missing: list[str] = []
    if not cfg.OWNER_NAME:
        missing.append("OWNER_NAME")
    if not cfg.OWNER_EMAIL:
        missing.append("OWNER_EMAIL")
    if missing:
        return StatusEntry(
            Status.WARN,
            "Owner profile",
            f"{', '.join(missing)} not set — From / Reply-To headers will be incomplete.",
        )
    return StatusEntry(Status.OK, "Owner profile", f"{cfg.OWNER_NAME} <{cfg.OWNER_EMAIL}>")
