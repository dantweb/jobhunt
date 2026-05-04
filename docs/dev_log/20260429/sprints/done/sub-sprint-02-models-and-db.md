# Sub-sprint 02 — Domain models + SQLite persistence

**Status:** PLANNED
**Parent:** [`sprint-01-jobhunt-mvp.md`](sprint-01-jobhunt-mvp.md)
**Depends on:** sub-sprint 01
**Unblocks:** sub-sprints 03, 04

---

## 1. Goal

Lock down the canonical data shapes the rest of the codebase will pivot
on, and put a real SQLite-backed persistence layer behind them with
idempotent dedupe semantics. Every later sub-sprint either produces or
consumes one of these types — getting them right (and tested) before the
HTTP and LLM layers land prevents a cascading rewrite.

## 2. Deliverables

- `jobhunt/models.py` — pydantic v2 models, all frozen where mutation has
  no business meaning:
  - `RawPosting` — what a `JobSource` returns. Required:
    `external_id`, `title`, `company`, `url`, `source` (short name).
    Optional (may be `None`, never absent): `description`,
    `salary_min_eur`, `salary_max_eur`, `location`, `language`,
    `posted_at`, `contact_email`, `apply_url`.
  - `Job` — canonical normalised posting. Same fields plus `id` (the
    dedupe hash) and `fetched_at`.
  - `Application` — one row per `(job_id, decision)` pair. Fields:
    `job_id`, `decision` (`pending|approved|rejected|skipped`),
    `cover_letter`, `sent_at`, `delivery` (`email|browser|None`),
    `notes`.
  - `RankResult` — `score: int [0, 100]`, `reason: str`,
    `flags: frozenset[str]` from a documented allowed set
    (`salary_unstated`, `german_only`, `seniority_mismatch`, …).
  - `Filters` — pydantic-settings model mirroring the `[filters]` block
    in `config.toml` (see parent §7).
  - `ProfileDraft` — what `LLMProvider.extract_profile()` returns:
    `min_salary_eur`, `allowed_locations`, `language_preference`,
    `language_fallback`, `seniority`, `stack_must_haves`. Each field has
    a documented default for when the LLM cannot derive it.
- `jobhunt/db.py` — SQLite schema + `connect(path: Path) -> sqlite3.Connection`.
  Schema migrations are inline (single `CREATE TABLE IF NOT EXISTS …`
  per table — no migration framework). Tables: `jobs`, `applications`.
  `jobs.id` is the dedupe hash; UNIQUE constraint enforces dedupe at the
  DB layer too.
- `jobhunt/repositories/job_repository.py` — `JobRepository`:
  - `save_many(jobs: Iterable[Job]) -> int` returns inserted count;
    `INSERT … ON CONFLICT(id) DO NOTHING`.
  - `shortlisted(limit: int = 20) -> list[Job]`.
  - `get(job_id: str) -> Job` (raises `JobNotFoundError`).
  - `mark_shortlisted(job_ids: Iterable[str]) -> None`.
- `jobhunt/repositories/application_repository.py` — `ApplicationRepository`:
  - `record_decision(app: Application) -> None`.
  - `pending() -> list[Application]`, `approved() -> list[Application]`.
  - `mark_sent(app_id, sent_at, delivery) -> None`.

## 3. TDD checkpoints

| Method                                    | Spec written first                                                                       |
|-------------------------------------------|------------------------------------------------------------------------------------------|
| `Job.dedupe_hash()`                       | same `(source, external_id)` AND same `(normalised_title, company, location)` produce same hash; different sources for the same posting collapse to one hash |
| `Filters` pydantic validation             | `min_salary_eur < 0` → `ValidationError`; empty `allowed_locations` → `ValidationError`  |
| `RankResult` validation                   | `score = -1` and `score = 101` raise; flags outside the allowed set raise                |
| `JobRepository.save_many()`               | inserts new rows; second call with same jobs returns 0 inserted; mixed batch (3 new + 2 dup) returns 3 |
| `JobRepository.shortlisted(limit)`        | returns only rows with `shortlisted = 1`; respects `limit`; sorted by `score DESC, fetched_at DESC` |
| `ApplicationRepository.record_decision()` | upsert by `(job_id)`; second `record_decision` for the same job overwrites               |
| `ApplicationRepository.mark_sent()`       | `pending → sent` transition only; calling on a `rejected` row raises                     |
| Integration: `tests/integration/test_db_schema.py` | spins up a real SQLite file in `tmp_path`, runs the full schema, exercises every repository method end-to-end |

## 4. Acceptance

1. All TDD checkpoints green.
2. Coverage on `jobhunt/models.py`, `jobhunt/db.py`,
   `jobhunt/repositories/` ≥ 95 % (these modules are pure logic — no
   excuse).
3. Schema is idempotent: running `db.connect()` twice on the same file
   does not error.
4. **No raw SQL in services or models** — only inside `db.py` and the two
   repository modules. CI grep check (added to `bin/pre-commit-check.sh`)
   enforces this.
5. `Filters` and `ProfileDraft` round-trip: `Filters(**draft.to_filters_dict())`
   produces a valid `Filters` object. Tested.

## 5. Out of scope

- Any HTTP, any LLM, any CV parsing.
- Migrations beyond initial schema. (If a column is added in a later
  sub-sprint, that sub-sprint owns its own migration line.)
- Async / connection pools — single connection per command run is fine.
