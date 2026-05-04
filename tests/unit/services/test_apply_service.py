from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest

from jobhunt.browser import Browser
from jobhunt.db import connect
from jobhunt.models import Application, Decision, Delivery, Job
from jobhunt.repositories import ApplicationRepository, JobRepository
from jobhunt.sender import Sender, SmtpConfig
from jobhunt.services import ApplyService
from tests.unit._fakes import make_raw, write_minimal_pdf


class CapturingSMTP:
    captured: ClassVar[list[object]] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def __enter__(self) -> CapturingSMTP:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self, context: object = None) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        return None

    def send_message(self, message: object) -> None:
        CapturingSMTP.captured.append(message)


def _smtp_config() -> SmtpConfig:
    return SmtpConfig(host="smtp.x", port=587, user="u", password="p", from_address="me@x.com")


@pytest.fixture
def setup(tmp_path: Path) -> Iterator[dict[str, object]]:
    conn = connect(tmp_path / "apply.sqlite")
    cv = write_minimal_pdf(tmp_path / "cv.pdf")
    yield {
        "conn": conn,
        "jobs": JobRepository(conn),
        "apps": ApplicationRepository(conn),
        "cv": cv,
        "tmp_path": tmp_path,
    }
    conn.close()


def _seed(jobs: JobRepository, raws: list, now: datetime) -> list[Job]:  # type: ignore[type-arg]
    jobs_list = [Job.from_raw(r, fetched_at=now) for r in raws]
    jobs.save_many(jobs_list)
    return jobs_list


def test_apply_via_email_sends_and_marks_sent(setup: dict[str, object]) -> None:
    CapturingSMTP.captured = []
    jobs = setup["jobs"]
    apps = setup["apps"]
    cv = setup["cv"]
    now = datetime(2026, 4, 29, tzinfo=UTC)
    seeded = _seed(jobs, [make_raw(idx=1, contact_email="hr@target.com")], now)  # type: ignore[arg-type]
    apps.record_decision(  # type: ignore[union-attr]
        Application(job_id=seeded[0].id, decision=Decision.APPROVED, cover_letter="body")
    )
    service = ApplyService(
        applications=apps,  # type: ignore[arg-type]
        jobs=jobs,  # type: ignore[arg-type]
        sender=Sender(config=_smtp_config(), owner_name="Me", smtp_factory=CapturingSMTP),  # type: ignore[arg-type]
        browser=Browser(opener=lambda _u: True),
        cv_path=cv,  # type: ignore[arg-type]
    )
    service.apply_via_email(apps.get(seeded[0].id))  # type: ignore[union-attr,arg-type]
    assert len(CapturingSMTP.captured) == 1
    stored = apps.get(seeded[0].id)  # type: ignore[union-attr]
    assert stored is not None
    assert stored.delivery == Delivery.EMAIL


def test_apply_via_browser_opens_url_and_marks_sent(setup: dict[str, object]) -> None:
    jobs = setup["jobs"]
    apps = setup["apps"]
    cv = setup["cv"]
    now = datetime(2026, 4, 29, tzinfo=UTC)
    seeded = _seed(jobs, [make_raw(idx=1, apply_url="https://target.com/apply")], now)  # type: ignore[arg-type]
    apps.record_decision(  # type: ignore[union-attr]
        Application(job_id=seeded[0].id, decision=Decision.APPROVED)
    )
    opened: list[str] = []
    service = ApplyService(
        applications=apps,  # type: ignore[arg-type]
        jobs=jobs,  # type: ignore[arg-type]
        sender=Sender(config=_smtp_config(), owner_name="Me", smtp_factory=CapturingSMTP),  # type: ignore[arg-type]
        browser=Browser(opener=lambda u: opened.append(u) or True),
        cv_path=cv,  # type: ignore[arg-type]
    )
    service.apply_via_browser(apps.get(seeded[0].id))  # type: ignore[union-attr,arg-type]
    assert opened == ["https://target.com/apply"]
    stored = apps.get(seeded[0].id)  # type: ignore[union-attr]
    assert stored is not None
    assert stored.delivery == Delivery.BROWSER


def test_run_dispatches_email_or_browser(setup: dict[str, object]) -> None:
    CapturingSMTP.captured = []
    jobs = setup["jobs"]
    apps = setup["apps"]
    cv = setup["cv"]
    now = datetime(2026, 4, 29, tzinfo=UTC)
    seeded = _seed(
        jobs,  # type: ignore[arg-type]
        [
            make_raw(idx=1, contact_email="hr@x.com"),
            make_raw(idx=2, contact_email=None, apply_url="https://x"),
        ],
        now,
    )
    for j in seeded:
        apps.record_decision(  # type: ignore[union-attr]
            Application(job_id=j.id, decision=Decision.APPROVED, cover_letter="body")
        )
    opened: list[str] = []
    service = ApplyService(
        applications=apps,  # type: ignore[arg-type]
        jobs=jobs,  # type: ignore[arg-type]
        sender=Sender(config=_smtp_config(), owner_name="Me", smtp_factory=CapturingSMTP),  # type: ignore[arg-type]
        browser=Browser(opener=lambda u: opened.append(u) or True),
        cv_path=cv,  # type: ignore[arg-type]
    )
    report = service.run()
    assert report.sent_email == 1
    assert report.opened_browser == 1
    assert len(CapturingSMTP.captured) == 1
    assert opened == ["https://x"]


def test_daily_cap_skips_extra_emails(setup: dict[str, object]) -> None:
    CapturingSMTP.captured = []
    jobs = setup["jobs"]
    apps = setup["apps"]
    cv = setup["cv"]
    # Real wall-clock — production `emails_sent_in_last_24h()` reads `now`
    # at call time, so a fixed past date would drift outside the 24 h window.
    now = datetime.now(tz=UTC)
    pre_existing = _seed(jobs, [make_raw(idx=99, contact_email="x@y.com")], now)  # type: ignore[arg-type]
    apps.record_decision(  # type: ignore[union-attr]
        Application(job_id=pre_existing[0].id, decision=Decision.APPROVED)
    )
    apps.mark_sent(pre_existing[0].id, now - timedelta(hours=2), Delivery.EMAIL)  # type: ignore[union-attr]

    seeded = _seed(jobs, [make_raw(idx=i, contact_email=f"hr-{i}@x.com") for i in range(11)], now)  # type: ignore[arg-type]
    for j in seeded:
        apps.record_decision(  # type: ignore[union-attr]
            Application(job_id=j.id, decision=Decision.APPROVED, cover_letter="body")
        )
    service = ApplyService(
        applications=apps,  # type: ignore[arg-type]
        jobs=jobs,  # type: ignore[arg-type]
        sender=Sender(config=_smtp_config(), owner_name="Me", smtp_factory=CapturingSMTP),  # type: ignore[arg-type]
        browser=Browser(opener=lambda _u: True),
        cv_path=cv,  # type: ignore[arg-type]
        daily_cap=10,
    )
    report = service.run()
    assert report.sent_email == 9
    assert report.skipped_daily_cap == 2
