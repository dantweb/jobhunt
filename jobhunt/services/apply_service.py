from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from jobhunt.browser import Browser
from jobhunt.exceptions import SmtpSendError
from jobhunt.models import Application, Delivery
from jobhunt.repositories import ApplicationRepository, JobRepository
from jobhunt.sender import Sender


@dataclass
class ApplyReport:
    sent_email: int = 0
    opened_browser: int = 0
    skipped_daily_cap: int = 0
    failures: dict[str, str] = field(default_factory=dict)


class ApplyService:
    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        jobs: JobRepository,
        sender: Sender,
        browser: Browser,
        cv_path: Path,
        daily_cap: int = 10,
    ) -> None:
        self._applications = applications
        self._jobs = jobs
        self._sender = sender
        self._browser = browser
        self._cv_path = cv_path
        self._daily_cap = daily_cap

    def apply_via_email(self, application: Application) -> None:
        job = self._jobs.get(application.job_id)
        contact = job.contact_email
        if not contact:
            raise SmtpSendError(f"job {job.id} has no contact_email")
        subject = f"Application: {job.title} at {job.company}"
        self._sender.send(application, to_address=contact, subject=subject, cv_path=self._cv_path)
        now = datetime.now(tz=UTC)
        self._applications.mark_sent(application.job_id, now, Delivery.EMAIL)

    def apply_via_browser(self, application: Application) -> None:
        job = self._jobs.get(application.job_id)
        url = job.apply_url or job.url
        self._browser.open(url)
        now = datetime.now(tz=UTC)
        self._applications.mark_sent(application.job_id, now, Delivery.BROWSER)

    def run(self) -> ApplyReport:
        report = ApplyReport()
        approved = self._applications.approved()
        for application in approved:
            job = self._jobs.get(application.job_id)
            if job.contact_email:
                already_sent = self._applications.emails_sent_in_last_24h()
                if already_sent >= self._daily_cap:
                    report.skipped_daily_cap += 1
                    continue
                try:
                    self.apply_via_email(application)
                    report.sent_email += 1
                except SmtpSendError as exc:
                    report.failures[application.job_id] = repr(exc)
            else:
                try:
                    self.apply_via_browser(application)
                    report.opened_browser += 1
                except Exception as exc:
                    report.failures[application.job_id] = repr(exc)
        return report
