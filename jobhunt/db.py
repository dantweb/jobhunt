"""SQLite schema + connection factory."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    external_id     TEXT NOT NULL,
    source          TEXT NOT NULL,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    url             TEXT NOT NULL,
    description     TEXT,
    salary_min_eur  INTEGER,
    salary_max_eur  INTEGER,
    location        TEXT,
    language        TEXT,
    posted_at       TEXT,
    contact_email   TEXT,
    apply_url       TEXT,
    fetched_at      TEXT NOT NULL,
    score           INTEGER,
    score_reason    TEXT,
    score_flags     TEXT,
    shortlisted     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_jobs_shortlisted ON jobs(shortlisted, score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_unscored ON jobs(score) WHERE score IS NULL;

CREATE TABLE IF NOT EXISTS applications (
    job_id          TEXT PRIMARY KEY,
    decision        TEXT NOT NULL DEFAULT 'pending',
    cover_letter    TEXT,
    sent_at         TEXT,
    delivery        TEXT,
    notes           TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_applications_decision ON applications(decision);
CREATE INDEX IF NOT EXISTS idx_applications_sent_at ON applications(sent_at);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
