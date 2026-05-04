"""Configuration: env vars (`.env`) + filters/sources (`config.toml`)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from jobhunt.models import Filters
from jobhunt.sender import SmtpConfig


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    LLM_PROVIDER: Literal["anthropic", "openai"] = "anthropic"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL_RANK: str = "claude-haiku-4-5"
    ANTHROPIC_MODEL_TAILOR: str = "claude-sonnet-4-6"
    ANTHROPIC_MODEL_PROFILE: str = "claude-sonnet-4-6"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_RANK: str = "gpt-4o-mini"
    OPENAI_MODEL_TAILOR: str = "gpt-4o"
    OPENAI_MODEL_PROFILE: str = "gpt-4o"

    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    JOOBLE_API_KEY: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_STARTTLS: bool = True

    CV_PATH: str = "/app/cv.pdf"
    OWNER_NAME: str = ""
    OWNER_EMAIL: str = ""

    DB_PATH: str = "/app/jobhunt.sqlite"
    CONFIG_PATH: str = "/app/config.toml"

    def smtp(self) -> SmtpConfig:
        return SmtpConfig(
            host=self.SMTP_HOST,
            port=self.SMTP_PORT,
            user=self.SMTP_USER,
            password=self.SMTP_PASSWORD,
            from_address=self.SMTP_FROM or self.OWNER_EMAIL,
            use_starttls=self.SMTP_USE_STARTTLS,
        )

    def cv_path(self) -> Path:
        return Path(self.CV_PATH)

    def db_path(self) -> Path:
        return Path(self.DB_PATH)

    def config_toml_path(self) -> Path:
        return Path(self.CONFIG_PATH)


class TomlConfig(BaseSettings):
    """Loaded from `config.toml`. Filters + active sources."""

    filters: Filters = Field(...)
    sources_enabled: list[str] = Field(default_factory=list)


def load_toml(path: Path) -> TomlConfig:
    if not path.exists():
        raise FileNotFoundError(f"config.toml not found at {path}")
    data = tomllib.loads(path.read_text())
    filters = Filters.model_validate(data.get("filters", {}))
    sources = list((data.get("sources") or {}).get("enabled") or [])
    return TomlConfig(filters=filters, sources_enabled=sources)


def write_toml(path: Path, *, filters: Filters, sources_enabled: list[str]) -> None:
    """Persist filters + sources to `config.toml`."""
    parts: list[str] = ["[filters]"]
    parts.append(f"min_salary_eur = {filters.min_salary_eur}")
    parts.append(_toml_list("allowed_locations", filters.allowed_locations))
    parts.append(f'language_preference = "{filters.language_preference}"')
    parts.append(f'language_fallback = "{filters.language_fallback}"')
    parts.append(_toml_list("seniority", filters.seniority))
    parts.append(_toml_list("stack_must_haves", filters.stack_must_haves))
    parts.append(f"shortlist_size = {filters.shortlist_size}")
    parts.append("")
    parts.append("[sources]")
    parts.append(_toml_list("enabled", sources_enabled))
    path.write_text("\n".join(parts) + "\n")


def _toml_list(key: str, items: list[str]) -> str:
    quoted = ", ".join(f'"{item}"' for item in items)
    return f"{key} = [{quoted}]"
