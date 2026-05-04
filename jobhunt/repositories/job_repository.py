from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime

from jobhunt.exceptions import JobNotFoundError
from jobhunt.models import Job, RankResult


def _row_to_job(row: sqlite3.Row) -> Job:
    posted_at_raw = row["posted_at"]
    fetched_at_raw = row["fetched_at"]
    flags_raw = row["score_flags"]
    return Job(
        id=row["id"],
        external_id=row["external_id"],
        source=row["source"],
        title=row["title"],
        company=row["company"],
        url=row["url"],
        description=row["description"],
        salary_min_eur=row["salary_min_eur"],
        salary_max_eur=row["salary_max_eur"],
        location=row["location"],
        language=row["language"],
        posted_at=datetime.fromisoformat(posted_at_raw) if posted_at_raw else None,
        contact_email=row["contact_email"],
        apply_url=row["apply_url"],
        fetched_at=datetime.fromisoformat(fetched_at_raw),
        score=row["score"],
        score_reason=row["score_reason"],
        score_flags=frozenset(json.loads(flags_raw)) if flags_raw else frozenset(),
        shortlisted=bool(row["shortlisted"]),
    )


class JobRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_many(self, jobs: Iterable[Job]) -> int:
        rows = [
            (
                j.id,
                j.external_id,
                j.source,
                j.title,
                j.company,
                j.url,
                j.description,
                j.salary_min_eur,
                j.salary_max_eur,
                j.location,
                j.language,
                j.posted_at.isoformat() if j.posted_at else None,
                j.contact_email,
                j.apply_url,
                j.fetched_at.isoformat(),
            )
            for j in jobs
        ]
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO jobs (
                id, external_id, source, title, company, url, description,
                salary_min_eur, salary_max_eur, location, language, posted_at,
                contact_email, apply_url, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return self._conn.total_changes - before

    def get(self, job_id: str) -> Job:
        cur = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        if row is None:
            raise JobNotFoundError(job_id)
        return _row_to_job(row)

    def shortlisted(self, limit: int = 20) -> list[Job]:
        cur = self._conn.execute(
            """
            SELECT * FROM jobs
            WHERE shortlisted = 1
            ORDER BY score DESC, fetched_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [_row_to_job(row) for row in cur.fetchall()]

    def unscored(self) -> list[Job]:
        cur = self._conn.execute("SELECT * FROM jobs WHERE score IS NULL")
        return [_row_to_job(row) for row in cur.fetchall()]

    def update_score(self, job_id: str, result: RankResult) -> None:
        self._conn.execute(
            "UPDATE jobs SET score = ?, score_reason = ?, score_flags = ? WHERE id = ?",
            (result.score, result.reason, json.dumps(sorted(result.flags)), job_id),
        )
        self._conn.commit()

    def mark_shortlisted(self, job_ids: Iterable[str]) -> None:
        ids = list(job_ids)
        if not ids:
            self._conn.execute("UPDATE jobs SET shortlisted = 0")
            self._conn.commit()
            return
        placeholders = ",".join("?" * len(ids))
        self._conn.execute("UPDATE jobs SET shortlisted = 0")
        self._conn.execute(
            f"UPDATE jobs SET shortlisted = 1 WHERE id IN ({placeholders})",
            ids,
        )
        self._conn.commit()

    def all(self) -> list[Job]:
        cur = self._conn.execute("SELECT * FROM jobs")
        return [_row_to_job(row) for row in cur.fetchall()]
