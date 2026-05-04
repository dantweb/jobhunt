# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repo is in **planning phase**. There is no source code, no
`pyproject.toml`, no tests yet. The plan lives in
`docs/dev_log/20260429/`:

- `status.md` — **start here**. Index of which sub-sprints are done /
  in-progress / planned. Updated whenever a sub-sprint moves to
  `sprints/done/`.
- `sprints/sprint-01-jobhunt-mvp.md` — master sprint with the binding
  engineering rules, architecture diagram, and acceptance gate.
- `sprints/sub-sprint-0N-*.md` — seven sub-sprints, each self-contained
  with its own TDD checkpoints and acceptance criteria. Linear chain
  01 → 02 → 03 → 04 → 05 → 06 → 07, with 03/04 parallel after 02.
- `sprints/done/` — completed sub-sprints (file is `git mv`'d here on
  acceptance, and the corresponding row in `status.md` is flipped to ✅).

**When picking up work:** read `status.md`, find the lowest-numbered
non-done sub-sprint, read that sub-sprint file, then read the master
sprint for the binding rules. Do not start implementation without reading
the master sprint at least once.

**When closing a sub-sprint:** flip its `Status:` header to `DONE`, add a
`Completed:` date, `git mv` it into `sprints/done/`, and update both the
status row and the **Last updated** date at the top of `status.md`.

## Project overview

`jobhunt` is a personal, single-user **interactive Python CLI** that:
fetches German + EU-remote backend job postings from free public APIs →
ranks them against the owner's CV using a pluggable LLM provider (Anthropic
or OpenAI) → presents the top 20 in a terminal review loop → tailors a
cover letter (EN or DE) for approved entries → sends via SMTP when a contact
email is exposed, or opens the apply URL in a browser otherwise.

State lives in **SQLite**. There is no daemon, no web UI, no queue, no cron.
Each invocation runs one command and exits.

## Architecture (planned, see sprint doc §5 for diagram)

Layered, with strict dependency inversion:

- **CLI (`cli.py`, Typer)** — thin argument parsing, delegates to a service.
- **Services** — `FetchService`, `ReviewService`, `ApplyService`. Each
  receives all collaborators via constructor injection.
- **Repositories** — `JobRepository`, `ApplicationRepository` over SQLite.
- **Polymorphic boundaries** — two ABCs that drive most of the design:
  - `JobSource` (one impl per source: bundesagentur, arbeitnow, adzuna,
    jooble, remotive, weworkremotely). Adding a source must require **zero
    edits** to `FetchService`. The active set is configurable via
    `config.toml`'s `[sources] enabled = [...]`.
  - `LLMProvider` (anthropic, openai), three methods: `rank()`, `tailor()`,
    `extract_profile()`. Adding a provider must require **zero edits** to
    `Ranker`, `Tailor`, or `ProfileSeeder`.
- **Wiring** — all concrete classes are constructed in **one** file,
  `jobhunt/wiring.py`. No service locator, no DI container, no module-level
  singletons. Tests inject fakes through the same constructors — never via
  monkey-patching imports.
- **Filtering vs. ranking** — `Ranker` applies hard filters (salary,
  location, language, seniority, stack) **before** any LLM call (cost
  control). The LLM provides only the soft score on survivors.
- **Filters are configurable, CV-seeded** — the `[filters]` block in
  `config.toml` is the single source of truth. `jobhunt init` bootstraps
  it by reading `CV_PATH` (PDF → text via `cv/reader.py`) and calling
  `LLMProvider.extract_profile()` (`cv/profile_seeder.py`). The user
  confirms/edits the values before they are written. **Never hardcode a
  filter value anywhere outside `config.toml`** — `Ranker` reads them via
  an injected `Filters` model; tests inject their own.

## Binding engineering rules

These come from the sprint plan §4 and are **non-negotiable** for every
deliverable:

- **TDD-first.** Spec before implementation. Write the failing pytest, watch
  it fail, then implement the minimum to pass. No production code without a
  covering test. `pytest --cov` ≥ 90 % on `jobhunt/` (excluding `cli.py`).
- **Liskov contract tests** are mandatory for the two ABCs:
  - `tests/unit/llm/test_provider_contract.py` — parametrised over every
    `LLMProvider` subclass. Asserts return-type postconditions, value ranges
    (`0 ≤ score ≤ 100`), allowed flag set, and error-type behaviour.
  - `tests/unit/sources/test_source_contract.py` — same idea for every
    `JobSource` subclass.
  A new provider/source cannot merge until it passes the shared contract test.
- **SOLID, in particular**:
  - A `JobSource` only speaks HTTP — it does not touch DB, dedupe, or score.
  - A `LLMProvider` only does prompt format + SDK call + response parse —
    it does not read the CV from disk or apply policy.
  - `Sender` does only SMTP, `Browser` does only `webbrowser.open`,
    `ApplyService` decides which to call. **No flag arguments**
    (`apply(send_email=True)` is forbidden — split into two methods).
- **DRY thresholds** — one HTTP client factory in `sources/_http.py`, one
  pydantic-settings class in `config.py`, one `RawPosting → Job` normaliser.
  Two near-identical lines is fine; **three is the promotion trigger**.
- **No over-engineering** — no async event bus, no plugin manager, no
  retries beyond a single retry-on-5xx, no circuit breakers, no Postgres
  swap-out abstraction. SQLite from stdlib is enough.
- **Naming** — full, pronounceable identifiers (`fetchAllSources`, not
  `fetchAll`; `applicationContactEmail`, not `email`). No single-letter
  variables, no cryptic abbreviations. Functions ≤ 30 lines.
- **Comments** — only the *why*, never the *what*. No ticket references, no
  "added for X flow", no `# removed` markers.
- **Forbidden without explicit written approval in the PR description**:
  `# type: ignore`, `# noqa`. CI fails on any warning from `ruff` or
  `mypy --strict`.
- **Drop deprecated** — delete, don't comment out. Git history is the audit
  log. Commit + push directly to `main` (no `feature/foo` branches for this
  personal repo).

## Planned CLI surface (from sprint doc §8)

```
jobhunt init                # one-time interactive setup → .env + config.toml
jobhunt fetch               # pull → dedupe → rank → mark top 20 shortlisted
jobhunt review              # interactive walk-through of shortlist
jobhunt send                # send approved via SMTP / open URL otherwise
jobhunt status              # pending / approved / sent / manual counts
jobhunt                     # alias for `fetch && review && send`
```

Review keys: `a` approve · `r` reject · `s` skip · `v` view full ad · `l`
letter preview · `q` quit & save state.

## Runtime: Docker-only (non-negotiable)

**The host runs Docker; nothing else.** Never invoke `uv`, `python`,
`pytest`, `ruff`, or `mypy` directly on the host — those tools live
inside the container built from the committed `Dockerfile`. This applies
to local development, the pre-commit gate, and GitHub Actions CI.

Every gate runs through `bin/pre-commit-check.sh`, which is the **single
source of truth** for orchestration. The script:

1. Runs `docker compose build jobhunt`.
2. Runs `docker compose run --rm jobhunt bash -lc '…'` with the full
   gate (`uv sync` → `ruff check` → `ruff format --check` →
   `mypy --strict` → `pytest tests/unit` with coverage gate ≥ 90 % →
   `pytest tests/integration`).

The GitHub Actions workflow at `.github/workflows/ci.yml` has **one
step**: invoke the same script. CI does not re-encode the gate in YAML.

The CI step **blanks every `*_API_KEY` and `SMTP_*` env var** so a
leaked key can never accidentally hit a live API — every external call
must be faked in-process. The §9.5 real-Bundesagentur smoke is
local-only, never in CI.

Tooling (all installed inside the image): **uv-managed**, Python 3.11+,
Typer for CLI, pydantic-settings for config, `respx` for HTTP fakes in
unit tests, `aiosmtpd` for an in-process SMTP server in `Sender` tests,
`pdfplumber` for CV PDF reading.

## Out of scope for v1 (do not implement)

LinkedIn / StepStone / XING scraping (ToS); recruiter-reply parsing; web UI;
daemon / cron; multi-user / SaaS; Postgres backend; free-text salary parsing
(v1 uses only structured salary fields, soft signals go to the LLM); separate
translation step (language is handled by picking the EN or DE cover-letter
template).

## Owner-supplied inputs (configured at runtime, not in the repo)

The following are configured by each user via `.env` and `config.toml`,
seeded by `jobhunt init`:

- CV PDF — `CV_PATH` env var. Default `/app/var/cv/cv.pdf` (bind-mounted
  from the host).
- Cover-letter style is learned from the CV by `LLMProvider.extract_profile()`.
- Filter values (salary floor, allowed locations, stack must-haves, seniority,
  language preference) live in `config.toml` and are seeded from the CV at
  `jobhunt init` time.
