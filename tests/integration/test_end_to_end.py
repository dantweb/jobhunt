"""End-to-end test: real SQLite + real services + fakes for HTTP/LLM/SMTP/browser."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from jobhunt.browser import Browser
from jobhunt.db import connect
from jobhunt.models import Decision, Filters, RankResult
from jobhunt.ranker import Ranker
from jobhunt.repositories import ApplicationRepository, JobRepository
from jobhunt.sender import Sender, SmtpConfig
from jobhunt.services import ApplyService, FetchService, ReviewService
from jobhunt.tailor import Tailor
from tests.unit._fakes import FakeJobSource, FakeLLMProvider, make_raw, write_minimal_pdf


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


def test_fetch_review_send_full_flow(tmp_path: Path) -> None:
    CapturingSMTP.captured = []
    conn = connect(tmp_path / "e2e.sqlite")
    cv_path = write_minimal_pdf(tmp_path / "cv.pdf")
    jobs = JobRepository(conn)
    apps = ApplicationRepository(conn)
    filters = Filters(
        min_salary_eur=0,
        allowed_locations=["remote"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )
    llm = FakeLLMProvider(rank_result=RankResult(score=85, reason="strong"))
    sources = [
        FakeJobSource(
            [
                make_raw(
                    idx=1,
                    title="Senior Python Engineer",
                    contact_email="hr@target.com",
                    location="Remote",
                ),
                make_raw(
                    idx=2,
                    title="Senior Python Lead",
                    apply_url="https://target.com/apply",
                    contact_email=None,
                    location="Remote",
                ),
            ]
        )
    ]
    ranker = Ranker(llm=llm, filters=filters, cv="CV TEXT")
    tailor = Tailor(llm=llm, cv="CV TEXT")
    fetch_service = FetchService(sources=sources, jobs=jobs, ranker=ranker, shortlist_size=10)
    review_service = ReviewService(jobs=jobs, applications=apps, tailor=tailor)
    apply_service = ApplyService(
        applications=apps,
        jobs=jobs,
        sender=Sender(
            config=SmtpConfig(host="x", port=587, user="u", password="p", from_address="me@x"),
            owner_name="Me",
            smtp_factory=CapturingSMTP,  # type: ignore[arg-type]
        ),
        browser=Browser(opener=lambda _u: True),
        cv_path=cv_path,
    )

    fetch_report = fetch_service.run()
    assert fetch_report.shortlisted >= 1

    items = list(review_service.next())
    assert items
    for item in items:
        review_service.record(job_id=item.job.id, decision=Decision.APPROVED)

    apply_report = apply_service.run()
    assert apply_report.sent_email == 1
    assert apply_report.opened_browser == 1
    assert len(CapturingSMTP.captured) == 1

    sent_apps = [a for a in apps.all() if a.sent_at is not None]
    assert len(sent_apps) == 2
    conn.close()


def test_fetch_review_send_with_real_db_persistence_across_steps(tmp_path: Path) -> None:
    """Reopen the DB between phases — proves state survives."""
    db_path = tmp_path / "persist.sqlite"
    cv_path = write_minimal_pdf(tmp_path / "cv.pdf")
    raw = make_raw(idx=1, contact_email="hr@x.com", location="Remote")
    filters = Filters(
        min_salary_eur=0,
        allowed_locations=["remote"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )

    conn = connect(db_path)
    jobs = JobRepository(conn)
    apps = ApplicationRepository(conn)
    llm = FakeLLMProvider(rank_result=RankResult(score=80, reason="ok"))
    ranker = Ranker(llm=llm, filters=filters, cv="CV")
    fetch_service = FetchService(
        sources=[FakeJobSource([raw])],
        jobs=jobs,
        ranker=ranker,
        shortlist_size=5,
    )
    fetch_service.run()
    conn.close()

    conn = connect(db_path)
    jobs = JobRepository(conn)
    apps = ApplicationRepository(conn)
    tailor = Tailor(llm=llm, cv="CV")
    review_service = ReviewService(jobs=jobs, applications=apps, tailor=tailor)
    items = list(review_service.next())
    assert len(items) == 1
    review_service.record(job_id=items[0].job.id, decision=Decision.APPROVED)
    conn.close()

    conn = connect(db_path)
    jobs = JobRepository(conn)
    apps = ApplicationRepository(conn)
    CapturingSMTP.captured = []
    apply_service = ApplyService(
        applications=apps,
        jobs=jobs,
        sender=Sender(
            config=SmtpConfig(host="x", port=587, user="u", password="p", from_address="me@x"),
            owner_name="Me",
            smtp_factory=CapturingSMTP,  # type: ignore[arg-type]
        ),
        browser=Browser(opener=lambda _u: True),
        cv_path=cv_path,
    )
    report = apply_service.run()
    assert report.sent_email == 1
    conn.close()
