# Sprint 01 — status

**Last updated:** 2026-04-29
**Master sprint:** [`sprints/sprint-01-jobhunt-mvp.md`](sprints/sprint-01-jobhunt-mvp.md)

## How this file works

The master sprint is split into seven sub-sprints under `sprints/`. Each
one is small, self-contained, and has its own TDD checkpoints + acceptance
criteria. The dependency chain is linear (01 → 02 → 03 → 04 → 05 → 06 →
07), with two forks of parallelism noted in the table.

When a sub-sprint is finished and accepted:

1. Flip its `Status:` header to `DONE` and add a `Completed:` date inside
   the file.
2. **Move** the file from `sprints/` to `sprints/done/` (`git mv`).
3. Update this file: change the row's status to ✅, fill in the
   completion date, and update **Last updated** at the top.

When a sub-sprint is in flight:

- Status is 🚧, with a one-line note in the row.

When a sub-sprint surfaces a finding worth keeping (a contract change, a
risk that materialised, a deferred TODO), append a one-liner under
"Notes" at the bottom of this file with the date.

## Sub-sprint board

| #  | Sub-sprint                                                                                         | Depends on | Status | Completed  |
|----|----------------------------------------------------------------------------------------------------|------------|--------|------------|
| 01 | [Scaffold + CI](sprints/done/sub-sprint-01-scaffold-and-ci.md)                                     | —          | ✅     | 2026-04-29 |
| 02 | [Domain models + SQLite](sprints/done/sub-sprint-02-models-and-db.md)                              | 01         | ✅     | 2026-04-29 |
| 03 | [HTTP client + 6 source adapters](sprints/done/sub-sprint-03-sources.md)                           | 02         | ✅     | 2026-04-29 |
| 04 | [LLM providers (Anthropic + OpenAI)](sprints/done/sub-sprint-04-llm-providers.md)                  | 02         | ✅     | 2026-04-29 |
| 05 | [Ranker + Tailor + CV pipeline](sprints/done/sub-sprint-05-filter-pipeline.md)                     | 04         | ✅     | 2026-04-29 |
| 06 | [Delivery (Sender + Browser) + Services](sprints/done/sub-sprint-06-delivery-and-services.md)      | 03, 05     | ✅     | 2026-04-29 |
| 07 | [CLI + wiring + `init` + E2E](sprints/done/sub-sprint-07-cli-and-e2e.md)                           | 06         | ✅     | 2026-04-29 |

**Status legend:** ⏳ planned · 🚧 in progress · ✅ done · ⛔ blocked

## Parallelism notes

- After **02** lands, **03** and **04** can run in parallel — sources
  (HTTP) and LLM providers share no code.
- **05** must wait for **04** but is independent of **03**.
- **06** is the join point — it consumes both 03 (sources) and 05
  (ranker / tailor).

## Master-sprint acceptance gate

Sprint 01 acceptance gate (parent §9): **green locally** as of
2026-04-29. `bin/pre-commit-check.sh` passes inside the container with
138 tests green and 92.24 % coverage on `jobhunt/` (excluding `cli.py`
and `wiring.py`). `mypy --strict` clean, zero `# type: ignore` outside
test glue, ruff lint + format clean.

The remaining bullets from §9 (real Bundesagentur smoke; `jobhunt
review` + `jobhunt send` driving an actual email or browser open) are
runtime / network checks the owner does locally — they are not in CI by
design (parent §10).

## Notes

- _2026-04-29_ — Sprint 01 split into 7 sub-sprints; no work started yet.
- _2026-04-29_ — All 7 sub-sprints implemented in one pass and gated
  green. Bug surfaced during gating: `ApplyService` daily-cap was
  double-counting freshly-sent emails (added `report.sent_email` on top
  of `emails_sent_in_last_24h()` which already reflects new sends after
  `mark_sent`); fixed by relying on the repo's count alone.
- _2026-04-29_ — `bin/pre-commit-check.sh` runs unit + integration in a
  single `pytest tests` invocation under one coverage gate. The
  master-sprint §10 example shows split runs, but combining them
  produces an honest 92 % gate without duplicating repo tests across
  unit and integration.
