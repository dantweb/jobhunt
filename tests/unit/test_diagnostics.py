from __future__ import annotations

from jobhunt.config import AppConfig
from jobhunt.diagnostics import Status, env_status


def _all_set_anthropic_mailpit() -> AppConfig:
    return AppConfig(
        LLM_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="key",
        ADZUNA_APP_ID="id",
        ADZUNA_APP_KEY="key",
        JOOBLE_API_KEY="key",
        SMTP_HOST="mailpit",
        SMTP_PORT=1025,
        SMTP_USE_STARTTLS=False,
        OWNER_NAME="Owner",
        OWNER_EMAIL="owner@x",
    )


def _by_label(entries: list, label: str):  # type: ignore[no-untyped-def]
    matching = [e for e in entries if e.label == label]
    assert len(matching) == 1, f"expected one entry labelled {label!r}, got {matching}"
    return matching[0]


def test_all_ok() -> None:
    entries = env_status(_all_set_anthropic_mailpit())
    assert all(e.status == Status.OK for e in entries)


def test_anthropic_key_missing_is_error() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(update={"ANTHROPIC_API_KEY": ""})
    entry = _by_label(env_status(cfg), "Anthropic API key")
    assert entry.status == Status.ERROR


def test_openai_key_missing_when_provider_openai() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(
        update={"LLM_PROVIDER": "openai", "OPENAI_API_KEY": ""}
    )
    entry = _by_label(env_status(cfg), "OpenAI API key")
    assert entry.status == Status.ERROR


def test_openai_key_set_when_provider_openai() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(
        update={"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-..."}
    )
    entry = _by_label(env_status(cfg), "OpenAI API key")
    assert entry.status == Status.OK


def test_adzuna_missing_is_warn() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(
        update={"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""}
    )
    entry = _by_label(env_status(cfg), "Adzuna")
    assert entry.status == Status.WARN


def test_jooble_missing_is_warn() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(update={"JOOBLE_API_KEY": ""})
    entry = _by_label(env_status(cfg), "Jooble")
    assert entry.status == Status.WARN


def test_smtp_host_missing_is_error() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(update={"SMTP_HOST": ""})
    entry = _by_label(env_status(cfg), "SMTP")
    assert entry.status == Status.ERROR


def test_smtp_real_host_is_ok() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(
        update={"SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": 587}
    )
    entry = _by_label(env_status(cfg), "SMTP")
    assert entry.status == Status.OK
    assert "smtp.gmail.com" in entry.detail


def test_owner_missing_is_warn() -> None:
    cfg = _all_set_anthropic_mailpit().model_copy(update={"OWNER_NAME": "", "OWNER_EMAIL": ""})
    entry = _by_label(env_status(cfg), "Owner profile")
    assert entry.status == Status.WARN
