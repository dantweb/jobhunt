from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from typing import Any, ClassVar

import pytest
from typer.testing import CliRunner

import jobhunt.cli as cli_mod
from jobhunt.sender import Sender, SmtpConfig
from tests.unit._fakes import write_minimal_pdf


class CapturingSMTP:
    captured: ClassVar[list[EmailMessage]] = []

    def __init__(self, host: str, port: int, *args: Any, **kwargs: Any) -> None:
        self.host = host
        self.port = port

    def __enter__(self) -> CapturingSMTP:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def starttls(self, context: Any = None) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        return None

    def send_message(self, message: EmailMessage) -> None:
        CapturingSMTP.captured.append(message)


def test_send_test_sends_through_configured_smtp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    CapturingSMTP.captured = []
    cv = write_minimal_pdf(tmp_path / "cv.pdf")
    monkeypatch.setenv("CV_PATH", str(cv))
    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_USE_STARTTLS", "false")
    monkeypatch.setenv("SMTP_FROM", "jobhunt@local.test")
    monkeypatch.setenv("OWNER_NAME", "Test Owner")

    real_sender_init = Sender.__init__

    def patched_init(
        self: Sender,
        *,
        config: SmtpConfig,
        owner_name: str,
        smtp_factory: Any = None,
    ) -> None:
        real_sender_init(
            self,
            config=config,
            owner_name=owner_name,
            smtp_factory=CapturingSMTP,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(Sender, "__init__", patched_init)

    result = CliRunner().invoke(cli_mod.app, ["send-test", "--to", "hr@target.test"])
    assert result.exit_code == 0, result.stdout
    assert len(CapturingSMTP.captured) == 1
    msg = CapturingSMTP.captured[-1]
    assert msg["To"] == "hr@target.test"
    assert msg["Subject"] == "jobhunt SMTP test"
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert "mailpit" in result.stdout or "1025" in result.stdout


def test_send_test_fails_loudly_when_cv_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CV_PATH", str(tmp_path / "nope.pdf"))
    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.setenv("SMTP_PORT", "1025")
    result = CliRunner().invoke(cli_mod.app, ["send-test"])
    assert result.exit_code == 1
    assert "CV not found" in result.stdout
