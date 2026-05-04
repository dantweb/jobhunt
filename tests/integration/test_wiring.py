"""Wiring integration test: real DB, real wiring, fake LLM via monkeypatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import jobhunt.wiring as wiring_mod
from jobhunt.config import AppConfig, TomlConfig
from jobhunt.models import Filters
from jobhunt.wiring import _build_sources, build_container


def _filters() -> Filters:
    return Filters(
        min_salary_eur=0,
        allowed_locations=["remote"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )


def test_missing_credentials_skip_with_warning(tmp_path: Path) -> None:
    app = AppConfig(
        ANTHROPIC_API_KEY="key",
        ADZUNA_APP_ID="",
        ADZUNA_APP_KEY="",
        JOOBLE_API_KEY="",
        DB_PATH=str(tmp_path / "x.sqlite"),
        CONFIG_PATH=str(tmp_path / "x.toml"),
    )
    sources = _build_sources(["bundesagentur", "adzuna", "jooble"], app)
    names = {s.name for s in sources}
    assert names == {"bundesagentur"}


def test_unknown_source_name_skipped(tmp_path: Path) -> None:
    app = AppConfig(ANTHROPIC_API_KEY="key", DB_PATH=str(tmp_path / "x.sqlite"))
    sources = _build_sources(["bundesagentur", "no-such-source"], app)
    names = {s.name for s in sources}
    assert names == {"bundesagentur"}


def test_build_container_uses_chosen_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM_PROVIDER=openai picks OpenAIProvider; AnthropicProvider is not constructed."""
    constructed: list[str] = []

    real_anthropic = wiring_mod.AnthropicProvider
    real_openai = wiring_mod.OpenAIProvider

    def fake_anthropic(**kwargs: Any) -> Any:
        constructed.append("anthropic")
        return real_anthropic(**kwargs)

    def fake_openai(**kwargs: Any) -> Any:
        constructed.append("openai")
        return real_openai(**kwargs)

    monkeypatch.setattr(wiring_mod, "AnthropicProvider", fake_anthropic)
    monkeypatch.setattr(wiring_mod, "OpenAIProvider", fake_openai)

    app = AppConfig(
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="key",
        DB_PATH=str(tmp_path / "x.sqlite"),
    )
    toml = TomlConfig(filters=_filters(), sources_enabled=["bundesagentur"])
    container = build_container(app=app, toml=toml, cv_text="CV")
    assert constructed == ["openai"]
    assert container.llm is not None
