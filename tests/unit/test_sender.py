from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, ClassVar

import pytest

from jobhunt.exceptions import SmtpSendError
from jobhunt.models import Application, Decision
from jobhunt.sender import Sender, SmtpConfig
from tests.unit._fakes import write_minimal_pdf


class FakeSMTP:
    captured: ClassVar[list[EmailMessage]] = []
    starttls_called: ClassVar[bool] = False
    login_args: ClassVar[tuple[str, str] | None] = None

    def __init__(self, host: str, port: int, *args: Any, **kwargs: Any) -> None:
        self.host = host
        self.port = port

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def starttls(self, context: Any = None) -> None:
        FakeSMTP.starttls_called = True

    def login(self, user: str, password: str) -> None:
        FakeSMTP.login_args = (user, password)

    def send_message(self, message: EmailMessage) -> None:
        FakeSMTP.captured.append(message)


class FakeFailingSMTP(FakeSMTP):
    def send_message(self, message: EmailMessage) -> None:
        raise smtplib.SMTPResponseException(550, b"rejected")


def _config() -> SmtpConfig:
    return SmtpConfig(
        host="smtp.example.com",
        port=587,
        user="user",
        password="pw",
        from_address="me@example.com",
    )


def test_send_builds_correct_message(tmp_path: Path) -> None:
    FakeSMTP.captured = []
    FakeSMTP.starttls_called = False
    FakeSMTP.login_args = None
    cv = write_minimal_pdf(tmp_path / "cv.pdf")
    sender = Sender(config=_config(), owner_name="Me", smtp_factory=FakeSMTP)  # type: ignore[arg-type]
    app = Application(job_id="abc", decision=Decision.APPROVED, cover_letter="Hello,\nbody")
    sender.send(app, to_address="hr@target.com", subject="Application", cv_path=cv)

    assert FakeSMTP.starttls_called is True
    assert FakeSMTP.login_args == ("user", "pw")
    msg = FakeSMTP.captured[-1]
    assert msg["To"] == "hr@target.com"
    assert msg["Subject"] == "Application"
    assert "me@example.com" in str(msg["From"])
    assert msg["Reply-To"] == "me@example.com"
    assert msg["Message-ID"]
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "cv.pdf"


def test_send_skips_starttls_when_disabled(tmp_path: Path) -> None:
    """Mailpit / dev SMTP servers do not support STARTTLS — sending must work
    when use_starttls=False, with no STARTTLS handshake attempted."""
    FakeSMTP.captured = []
    FakeSMTP.starttls_called = False
    FakeSMTP.login_args = None
    cv = write_minimal_pdf(tmp_path / "cv.pdf")
    config = SmtpConfig(
        host="mailpit",
        port=1025,
        user="",
        password="",
        from_address="me@local",
        use_starttls=False,
    )
    sender = Sender(config=config, owner_name="Me", smtp_factory=FakeSMTP)  # type: ignore[arg-type]
    app = Application(job_id="abc", decision=Decision.APPROVED, cover_letter="body")
    sender.send(app, to_address="hr@target", subject="x", cv_path=cv)
    assert FakeSMTP.starttls_called is False
    assert FakeSMTP.login_args is None
    assert len(FakeSMTP.captured) == 1


def test_send_raises_smtp_send_error_on_5xx(tmp_path: Path) -> None:
    cv = write_minimal_pdf(tmp_path / "cv.pdf")
    sender = Sender(config=_config(), owner_name="Me", smtp_factory=FakeFailingSMTP)  # type: ignore[arg-type]
    app = Application(job_id="abc", decision=Decision.APPROVED, cover_letter="body")
    with pytest.raises(SmtpSendError):
        sender.send(app, to_address="hr@target.com", subject="x", cv_path=cv)


def test_send_raises_when_no_cover_letter(tmp_path: Path) -> None:
    cv = write_minimal_pdf(tmp_path / "cv.pdf")
    sender = Sender(config=_config(), owner_name="Me", smtp_factory=FakeSMTP)  # type: ignore[arg-type]
    app = Application(job_id="abc", decision=Decision.APPROVED, cover_letter=None)
    with pytest.raises(SmtpSendError):
        sender.send(app, to_address="hr@x", subject="x", cv_path=cv)


def test_send_raises_when_cv_missing(tmp_path: Path) -> None:
    sender = Sender(config=_config(), owner_name="Me", smtp_factory=FakeSMTP)  # type: ignore[arg-type]
    app = Application(job_id="abc", decision=Decision.APPROVED, cover_letter="body")
    with pytest.raises(SmtpSendError):
        sender.send(app, to_address="x@y", subject="x", cv_path=tmp_path / "absent.pdf")
