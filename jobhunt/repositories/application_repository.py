from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from jobhunt.exceptions import InvalidStateTransitionError, JobNotFoundError
from jobhunt.models import Application, Decision, Delivery


def _row_to_application(row: sqlite3.Row) -> Application:
    sent_at_raw = row["sent_at"]
    return Application(
        job_id=row["job_id"],
        decision=Decision(row["decision"]),
        cover_letter=row["cover_letter"],
        sent_at=datetime.fromisoformat(sent_at_raw) if sent_at_raw else None,
        delivery=Delivery(row["delivery"]) if row["delivery"] else None,
        notes=row["notes"],
    )


class ApplicationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record_decision(self, app: Application) -> None:
        self._conn.execute(
            """
            INSERT INTO applications (job_id, decision, cover_letter, sent_at, delivery, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                decision = excluded.decision,
                cover_letter = excluded.cover_letter,
                sent_at = excluded.sent_at,
                delivery = excluded.delivery,
                notes = excluded.notes
            """,
            (
                app.job_id,
                str(app.decision),
                app.cover_letter,
                app.sent_at.isoformat() if app.sent_at else None,
                str(app.delivery) if app.delivery else None,
                app.notes,
            ),
        )
        self._conn.commit()

    def get(self, job_id: str) -> Application | None:
        cur = self._conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        return _row_to_application(row) if row else None

    def pending(self) -> list[Application]:
        return self._where("decision = 'pending'")

    def approved(self) -> list[Application]:
        return self._where("decision = 'approved' AND sent_at IS NULL")

    def all(self) -> list[Application]:
        return self._where("1 = 1")

    def _where(self, clause: str) -> list[Application]:
        cur = self._conn.execute(f"SELECT * FROM applications WHERE {clause}")
        return [_row_to_application(row) for row in cur.fetchall()]

    def mark_sent(self, job_id: str, sent_at: datetime, delivery: Delivery) -> None:
        cur = self._conn.execute("SELECT decision FROM applications WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        if row is None:
            raise JobNotFoundError(job_id)
        if row["decision"] != Decision.APPROVED.value:
            raise InvalidStateTransitionError(
                f"cannot mark_sent on application with decision={row['decision']!r}"
            )
        self._conn.execute(
            "UPDATE applications SET sent_at = ?, delivery = ? WHERE job_id = ?",
            (sent_at.isoformat(), str(delivery), job_id),
        )
        self._conn.commit()

    def emails_sent_in_last_24h(self, *, now: datetime | None = None) -> int:
        now = now or datetime.now(tz=UTC)
        threshold = (now - timedelta(hours=24)).isoformat()
        cur = self._conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM applications
            WHERE delivery = 'email' AND sent_at IS NOT NULL AND sent_at >= ?
            """,
            (threshold,),
        )
        row = cur.fetchone()
        return int(row["n"]) if row else 0
