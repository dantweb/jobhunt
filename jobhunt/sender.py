"""SMTP sender. Stdlib only — no third-party SMTP library."""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from jobhunt.exceptions import SmtpSendError
from jobhunt.models import Application


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_address: str
    use_starttls: bool = True


class Sender:
    def __init__(
        self,
        *,
        config: SmtpConfig,
        owner_name: str,
        smtp_factory: type[smtplib.SMTP] | None = None,
    ) -> None:
        self._config = config
        self._owner_name = owner_name
        self._smtp_factory = smtp_factory or smtplib.SMTP

    def send(
        self,
        application: Application,
        *,
        to_address: str,
        subject: str,
        cv_path: Path,
    ) -> None:
        if not application.cover_letter:
            raise SmtpSendError("application has no cover letter")
        message = self._build_message(
            to_address=to_address, subject=subject, body=application.cover_letter, cv_path=cv_path
        )
        try:
            with self._smtp_factory(self._config.host, self._config.port) as smtp:
                if self._config.use_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if self._config.user and self._config.password:
                    smtp.login(self._config.user, self._config.password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            raise SmtpSendError(f"send failed: {exc}") from exc

    def _build_message(
        self, *, to_address: str, subject: str, body: str, cv_path: Path
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = f"{self._owner_name} <{self._config.from_address}>"
        msg["To"] = to_address
        msg["Subject"] = subject
        msg["Reply-To"] = self._config.from_address
        msg["Message-ID"] = make_msgid(domain=self._config.from_address.split("@", 1)[-1])
        msg.set_content(body)
        if not cv_path.exists():
            raise SmtpSendError(f"CV file not found: {cv_path}")
        msg.add_attachment(
            cv_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=cv_path.name,
        )
        return msg
