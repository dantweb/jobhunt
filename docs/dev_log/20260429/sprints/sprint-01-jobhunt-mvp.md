# Sprint 01 — Jobhunt MVP (Interactive CLI)

**Status:** PLANNED — 2026-04-29
**Date:** 2026-04-29
**Repo:** `jobhunt` (NEW — standalone Python CLI tool)
**Owner:** the person running the tool (single-user by design)

---

## 1. Goal

Ship a personal, interactive CLI tool that:

1. **Fetches** German + EU-remote backend job postings from multiple free public sources.
2. **Ranks** each posting against the owner's CV using a pluggable LLM provider (Anthropic Claude or OpenAI).
3. **Shortlists** the top 20 matches per fetch run.
4. **Reviews** the shortlist interactively — owner approves / rejects / skips each entry from the terminal.
5. **Tailors** a cover letter (English or German, picked from the posting's language) for every approved entry.
6. **Sends** the CV + tailored letter via SMTP to postings that expose a contact email; for postings that only expose an apply URL, opens the URL in the default browser and marks the application as "manual".

A run is "successful" when the owner can sit down at the terminal, type
`jobhunt`, and within ~5 minutes have applied (auto + manual) to 5–10
high-quality openings without ever opening a browser tab manually.

### Owner profile (default filters — configurable, auto-seeded from CV)

All filter values below are **defaults only**. Every value is editable in
`config.toml`'s `[filters]` block (see §7). The values are not hardcoded
anywhere in the codebase — `Ranker` reads them via `Filters` (a
pydantic model), and tests inject custom `Filters` instances through the
constructor.

**Initial values are bootstrapped from the CV at `jobhunt init` time** —
the init command:

1. Reads the PDF at `CV_PATH` (PyMuPDF / `pdfplumber`, stdlib first).
2. Calls `LLMProvider.extract_profile(cv_text) -> ProfileDraft` (a third
   method on `LLMProvider`, contract-tested like `rank()` and `tailor()`).
3. Writes the resulting filter values into `config.toml` and shows them to
   the user for confirmation/edit before saving.
4. The user can re-run `jobhunt init --reseed` to regenerate from an
   updated CV without losing other config.

An example seeded result (illustrative only — real values come from your CV):

- **Salary floor:** €90 000 brutto / year. Postings without a stated salary
  are kept but flagged `salary_unstated`.
- **Location:** Remote, OR Hybrid in Karlsruhe / Frankfurt am Main /
  München, OR EU-remote.
- **Stack must-haves:** PHP / Symfony OR Python (either alone qualifies;
  both is a boost).
- **Working language:** prefers English-speaking environments. German is
  acceptable as the second working language. A posting that requires
  "Deutsch C2 / Muttersprache" without English is downweighted.
- **Seniority:** Senior, Lead, Staff, Principal.

These values are written into `config.toml` by `jobhunt init`; nothing in
the source tree references them directly.

---

## 2. Sources (all free, all public)

The active source set is **configurable** (see §7 — `[sources]` block in
`config.toml`). The list below is what ships **enabled by default**; users
can disable any of them, or enable additional sources that have an adapter
on disk, without code changes.

| Source                          | Coverage                                      | Auth       | Adapter file                    | Default |
|---------------------------------|-----------------------------------------------|------------|---------------------------------|---------|
| Bundesagentur für Arbeit API    | All German postings (broadest)                | None       | `sources/bundesagentur.py`      | enabled |
| Arbeitnow API                   | English-speaking tech jobs in DE              | None       | `sources/arbeitnow.py`          | enabled |
| Adzuna API                      | Aggregator (many DE boards)                   | Free key   | `sources/adzuna.py`             | enabled |
| Jooble API                      | Aggregator (DE)                               | Free key   | `sources/jooble.py`             | enabled |
| Remotive API                    | EU-remote tech roles                          | None       | `sources/remotive.py`           | enabled |
| WeWorkRemotely RSS              | EU-remote                                     | None       | `sources/weworkremotely.py`     | enabled |

Configuration model:

- **Adapter registry** — `sources/__init__.py` exposes a `REGISTRY: dict[str,
  type[JobSource]]` keyed by short name (e.g. `"bundesagentur"`,
  `"arbeitnow"`). Every `JobSource` subclass on disk is registered here.
- **Active set** — `config.toml`'s `[sources]` block lists which registered
  names to instantiate for a given run. `jobhunt init` writes the default
  set above on first setup; the user edits the file (or future
  `jobhunt sources enable/disable <name>` subcommands) to change it.
- **Credential gating** — a source whose required env vars are missing is
  **skipped with a warning** at wiring time (it is not a hard error), so a
  user without an Adzuna key can still run the other five.
- **Wiring** — `wiring.build_container(config)` reads the active set + the
  registry and constructs the concrete `JobSource` list passed to
  `FetchService`. `FetchService` itself is unaware of which sources exist.

LinkedIn, StepStone, XING are **out of scope** for v1 — their ToS forbids
automated access and their anti-bot systems are aggressive. The CLI may
later print a "manual check" reminder for those sources, but no
scraping in this sprint.

---

## 3. Repo structure

```
jobhunt/
├── Dockerfile                      # python:3.11-slim + uv; the only runtime
├── docker-compose.yml              # `jobhunt` dev service, source bind-mounted
├── .dockerignore
├── pyproject.toml                  # uv-managed, Python 3.11+
├── uv.lock                         # committed; reproducible builds
├── README.md                       # setup + usage (Docker-first)
├── .env.example                    # SMTP creds, API keys, LLM provider
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                  # invokes bin/pre-commit-check.sh — same script as local
├── docs/
│   └── dev_log/20260429/sprint-01-jobhunt-mvp.md   (this file)
├── jobhunt/
│   ├── __init__.py
│   ├── cli.py                      # Typer entry: init / fetch / review / send / status
│   ├── config.py                   # pydantic-settings: env + filters
│   ├── db.py                       # SQLite schema + connection
│   ├── models.py                   # dataclasses: Job, Application, Profile, Score
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py                 # JobSource ABC
│   │   ├── bundesagentur.py
│   │   ├── arbeitnow.py
│   │   ├── adzuna.py
│   │   ├── jooble.py
│   │   ├── remotive.py
│   │   └── weworkremotely.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                 # LLMProvider ABC: rank() / tailor() / extract_profile()
│   │   ├── anthropic_provider.py   # Claude impl with prompt caching
│   │   └── openai_provider.py      # OpenAI impl
│   ├── cv/
│   │   ├── __init__.py
│   │   ├── reader.py               # PDF → text (pdfplumber)
│   │   └── profile_seeder.py       # text → ProfileDraft via LLMProvider.extract_profile()
│   ├── ranker.py                   # uses LLMProvider.rank() + filters
│   ├── tailor.py                   # uses LLMProvider.tailor()
│   ├── sender.py                   # SMTP via stdlib
│   ├── browser.py                  # opens apply URL via webbrowser stdlib
│   ├── repositories/
│   │   ├── job_repository.py
│   │   └── application_repository.py
│   ├── services/
│   │   ├── fetch_service.py        # orchestrates sources + dedupe
│   │   ├── review_service.py       # interactive review loop
│   │   └── apply_service.py        # send / open-browser flow
│   └── prompts/
│       ├── rank.py                 # rank prompt template
│       └── tailor.py               # cover-letter prompt templates (en + de)
├── tests/
│   ├── conftest.py                 # fixtures: tmp sqlite, fake LLM, fake SMTP
│   ├── unit/
│   │   ├── sources/
│   │   │   ├── test_bundesagentur.py
│   │   │   ├── test_arbeitnow.py
│   │   │   ├── test_adzuna.py
│   │   │   ├── test_jooble.py
│   │   │   ├── test_remotive.py
│   │   │   └── test_weworkremotely.py
│   │   ├── llm/
│   │   │   ├── test_anthropic_provider.py
│   │   │   └── test_openai_provider.py
│   │   ├── cv/
│   │   │   ├── test_reader.py
│   │   │   └── test_profile_seeder.py
│   │   ├── test_ranker.py
│   │   ├── test_tailor.py
│   │   ├── test_sender.py
│   │   ├── test_repositories.py
│   │   └── services/
│   │       ├── test_fetch_service.py
│   │       ├── test_review_service.py
│   │       └── test_apply_service.py
│   ├── integration/
│   │   ├── test_db_schema.py       # real sqlite, real schema, real repos
│   │   ├── test_fetch_flow.py      # fakes for HTTP, real DB
│   │   └── test_apply_flow.py      # real DB, in-process SMTP fake
│   └── fixtures/
│       ├── bundesagentur_sample.json
│       ├── arbeitnow_sample.json
│       └── … (one per source)
└── bin/
    └── pre-commit-check.sh         # runs every gate INSIDE the container
```

### 3.1 Runtime: Docker-only

The host machine never runs Python, `uv`, or `pytest` directly for this
project. **Docker is the only supported runtime**, and the same image is
used for every workflow:

- Local development (`docker compose run --rm jobhunt …`).
- The pre-commit gate (`bin/pre-commit-check.sh`).
- GitHub Actions CI (which invokes the same script).

This is non-negotiable. The script is the single entry point — if it is
green on a developer's laptop, it must be green in CI, and vice versa.
There is no second code path that runs the tools "natively" on the host.

Reasons:

1. **Reproducibility** — version drift between developer laptops, the
   GitHub Actions runner, and (eventually) any cloud worker is impossible
   when everyone uses the pinned `Dockerfile`.
2. **Single source of truth** — `bin/pre-commit-check.sh` is the only
   place that orchestrates lint + type + unit + integration. CI does not
   re-encode the same steps in YAML.
3. **Onboarding** — a fresh checkout needs `docker` and nothing else; no
   pyenv / asdf / uv installation friction.

---

## 4. Core engineering requirements (binding for every deliverable)

These are non-negotiable. A deliverable is not "done" until every item is
satisfied for the code it touches.

### 4.1 TDD-first

- **Spec before implementation, no exceptions.**
- For every public function or method on a source adapter, LLM provider,
  repository, service, or CLI command:
  1. Write the failing pytest first.
  2. Run it. Watch it fail with the expected error (not an `ImportError`
     from a missing module — write the empty stub first).
  3. Implement the minimum to pass.
  4. Refactor once green. Never "refactor now, test later."
- **No production code without a covering test.** `pytest --cov` must
  show ≥ 90 % line coverage on `jobhunt/` (excluding `cli.py` glue).
- If a test is hard to write, **redesign**. Hard-to-test code is a design
  smell, not a testing problem.

#### Method-specific TDD checkpoints

| Module                          | Spec written first                                                                       |
|---------------------------------|------------------------------------------------------------------------------------------|
| `BundesagenturSource.fetch()`   | happy path (1 page) + pagination + 5xx retry (single retry, then raise)                  |
| `ArbeitnowSource.fetch()`       | happy path + empty result set + JSON shape change (extra field tolerated)                |
| `AdzunaSource.fetch()`          | happy path + missing API key → raises `MissingCredentialsError` BEFORE network call      |
| `Job.dedupe_hash()`             | same posting from two sources produces same hash → only one row in DB                    |
| `JobRepository.save_many()`     | dedupe by hash; second save is no-op (`INSERT … ON CONFLICT DO NOTHING`)                 |
| `AnthropicProvider.rank()`      | returns `RankResult(score, reason, flags)`; flags include `salary_unstated` when missing |
| `OpenAIProvider.rank()`         | identical contract to AnthropicProvider — Liskov check below                             |
| `Ranker.score(job)`             | applies hard filters (salary, location) BEFORE calling LLM (cost-saving)                 |
| `Tailor.write(job, language)`   | EN posting → English letter; DE posting → German letter; mixed → owner-preference (EN)   |
| `CvReader.read(path)`           | extracts plain text from PDF; raises `MissingCvError` if `path` does not exist           |
| `ProfileSeeder.seed(cv_text)`   | returns `ProfileDraft` with salary_floor / locations / stack / seniority / language fields populated; missing fields → sensible defaults documented in code |
| `LLMProvider.extract_profile()` | shared contract test asserts `ProfileDraft` shape across Anthropic + OpenAI impls        |
| `Sender.send(application)`      | builds RFC 5322 message, attaches CV PDF, raises on SMTP 5xx                             |
| `ReviewService.next()`          | yields one shortlisted application at a time; persists owner's decision before yielding next |
| `ApplyService.apply(approved)`  | email contact → calls `Sender`; URL only → calls `Browser`, marks `manual`               |

Frontend tests: N/A (CLI only).

### 4.2 SOLID

#### S — Single responsibility
- A `JobSource` adapter speaks **only** its source's HTTP API. It does
  not touch the DB, does not score, does not dedupe.
- A `LLMProvider` does **only** prompt formatting + SDK call + response
  parsing. It does not read the CV from disk, does not save results, does
  not decide policy.
- `Ranker` applies **filter policy**; `LLMProvider` applies the model.
  Two responsibilities, two classes.
- `Sender` does **only** SMTP. `Browser` does **only** open URLs.
  `ApplyService` decides which to call.
- CLI commands in `cli.py` are thin: parse args → call a service →
  format output. No business logic.

#### O — Open / closed
- Adding a new job source = adding a file in `sources/` that subclasses
  `JobSource`, plus one line registering it in `sources/__init__.py`'s
  `REGISTRY`. **Zero edits** to `FetchService`. Enabling/disabling a
  registered source is a `config.toml` edit — also zero code changes.
- Adding a new LLM provider = adding a file in `llm/` that subclasses
  `LLMProvider`, plus one entry in the provider factory. **Zero edits**
  to `Ranker` or `Tailor`.
- Adding a new filter rule = adding a `FilterRule` subclass and
  registering it in the `Ranker` constructor list. No edits to existing
  rules.

#### L — Liskov substitution
- **Every `JobSource` subclass must honour every postcondition of the
  base interface.** A successful `fetch()` returns
  `Iterable[RawPosting]` where each item has `external_id`, `title`,
  `company`, `url`, and `source` populated. Optional fields may be
  `None`, but never absent. A subclass must never weaken this contract.
- **Every `LLMProvider` subclass must honour the same contract.**
  `AnthropicProvider.rank(job, cv, filters)` and
  `OpenAIProvider.rank(job, cv, filters)` must both return a
  `RankResult` of the same shape, with `score ∈ [0, 100]` and the same
  set of allowed `flags`. The Liskov check is enforced via a **shared
  contract test** parameterised over both providers
  (`tests/unit/llm/test_provider_contract.py`).
- A `MagicMock` standing in for a `JobRepository` in unit tests must
  raise the same exceptions the real repo raises (e.g.
  `DuplicateJobError`). Tests configure the mock accordingly — the LSP
  applies to test doubles, not just production subclasses.
- The contract test pattern:
  ```python
  @pytest.mark.parametrize("provider_factory", [
      lambda: AnthropicProvider(api_key="test", model="claude-haiku-4-5"),
      lambda: OpenAIProvider(api_key="test", model="gpt-4o-mini"),
  ])
  def test_rank_returns_valid_score(provider_factory, fake_http):
      provider = provider_factory()
      result = provider.rank(SAMPLE_JOB, SAMPLE_CV, DEFAULT_FILTERS)
      assert 0 <= result.score <= 100
      assert result.reason
      assert result.flags <= ALLOWED_FLAGS
  ```

#### I — Interface segregation
- `JobSource` exposes one method: `fetch() -> Iterable[RawPosting]`.
  No `parse()`, no `validate()`, no `save()` — those are not the
  source's concern.
- `LLMProvider` exposes two methods: `rank()` and `tailor()`. Anything
  the model needs internally (system prompt, prompt-cache key, retry
  config) is private to the implementation.
- The CLI never calls a repository directly — it calls a service. The
  service interface is narrow (one verb per service method).

#### D — Dependency inversion
- High-level modules (`FetchService`, `ReviewService`, `ApplyService`)
  depend on **abstractions** (`JobSource`, `LLMProvider`,
  `JobRepository`, `Sender`, `Browser`) — never on concrete classes.
- Concrete classes are wired in **one** place: `jobhunt/wiring.py`,
  using simple constructor injection. No service locator, no DI
  container.
- See §4.5.

### 4.3 DRY

- One HTTP client factory in `sources/_http.py`. Every source uses it.
  When a 7th source needs a different timeout policy, **then** parametrise
  — not before.
- One Pydantic-settings class for env in `config.py`. Sources read their
  keys from it; they do not parse `os.environ` themselves.
- One `RawPosting → Job` normaliser in `models.py`. Each source produces
  `RawPosting`; the normaliser maps to the canonical `Job`. Duplicate
  normalisation in source adapters is forbidden.
- One cover-letter template per language (`prompts/tailor.py`). Sources
  do not embed cover-letter strings.
- Two near-identical lines is fine. **Three is the promotion trigger.**

### 4.4 Liskov-specific contract enforcement

(Repeated here because the user explicitly called Liskov out.)

- A **single shared contract test module** per polymorphic interface:
  - `tests/unit/llm/test_provider_contract.py` — runs the same suite
    against `AnthropicProvider` and `OpenAIProvider`. Every new provider
    must pass it before merge.
  - `tests/unit/sources/test_source_contract.py` — runs the same suite
    against every `JobSource` subclass. Every new source must pass it.
- The contract test asserts:
  1. **Type postconditions** (return types, field presence, value ranges).
  2. **Behavioural postconditions** (idempotency where promised, error
     types raised on bad input).
  3. **No strengthened preconditions** (e.g. a provider may not require a
     longer CV than the base contract specifies).
- A subclass that fails the contract test fails CI. No exceptions, no
  conditional skips per provider.

### 4.5 Dependency injection

- Every service receives its collaborators through its constructor:
  ```python
  class FetchService:
      def __init__(
          self,
          sources: list[JobSource],
          job_repo: JobRepository,
          ranker: Ranker,
      ) -> None:
          ...
  ```
- No module-level singletons. No `from .somewhere import db` inside a
  service. The DB session, the LLM provider, the SMTP config — all
  injected.
- Wiring lives in **one** file, `jobhunt/wiring.py`. The CLI calls
  `wiring.build_container(config)` once at startup; everything else is
  constructed there.
- Tests inject fakes / mocks directly via the same constructors. No
  monkey-patching of imports, ever.

### 4.6 Clean Code

- **Full, pronounceable names.** Per `MEMORY.md`'s
  `feedback_variable_naming.md`:
  - `fetchAllSources`, not `fetchAll`.
  - `tailorCoverLetter`, not `tcl`.
  - `applicationContactEmail`, not `email` when ambiguous.
  - `germanLanguageRequiredFlag`, not `de_req`.
  - **No** single-letter variables. **No** cryptic abbreviations.
- Functions ≤ 30 lines. One level of abstraction per function.
- **No flag arguments.** `apply(send_email=True)` is forbidden — split
  into two methods (`apply_via_email`, `apply_via_browser`).
- **Zero "what" comments.** Identifiers say what. Only comment the
  **why** when it is non-obvious: a vendor-API quirk, an LLM
  prompt-caching invariant, a subtle race condition.
- No references to tickets / current callers in code comments.
- `ruff` (lint + format) and `mypy --strict` gate the repo. CI fails on
  any warning. **No `# type: ignore` or `# noqa` without explicit
  written approval** in the PR description (per
  `feedback_no_noqa_without_permission.md`).

### 4.7 No over-engineering

- No async event bus. No plugin manager. No message queue. The CLI runs
  one command, finishes, exits. SQLite holds state between runs.
- No retries beyond a single retry-on-5xx in the shared HTTP client.
- No circuit breakers, no rate-limiter abstractions. If a source rate-
  limits us, the source adapter sleeps the documented amount in-line.
- No web UI. No daemon. No cron. The owner runs `jobhunt` manually.
- No "swap SQLite for Postgres later" abstraction — `sqlite3` from
  stdlib is enough. If we ever need Postgres, we change one file.
- No feature flags. No config UI.

### 4.8 Drop deprecated

- Delete, don't comment out. No `# removed`, no `# @deprecated`. Git
  history is the audit log.
- Commit + push directly to `main` per `feedback_no_temp_branches.md`.
  No `feature/foo` branches for personal work in this repo.

---

## 5. Architecture (data flow + module responsibilities)

```
                                ┌──────────────────┐
                                │   cli.py (Typer) │
                                └────────┬─────────┘
                                         │ delegates
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
┌────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│   FetchService          │  │   ReviewService         │  │   ApplyService          │
│   ───────────           │  │   ───────────           │  │   ───────────           │
│ • for each JobSource:   │  │ • iterate shortlisted   │  │ • for each approved:    │
│     fetch() → save()    │  │ • prompt: a/r/s/v/l/q   │  │   if email → Sender    │
│ • Ranker.score(j)       │  │ • persist decision      │  │   else    → Browser    │
│ • mark top 20 shortlist │  │                         │  │ • persist sent_at      │
└────────┬───────────────┘  └─────────┬───────────────┘  └────────┬───────────────┘
         │                            │                           │
         ▼                            ▼                           ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      Repositories (JobRepository, ApplicationRepository)   │
│                              ──────── SQLite ────────                      │
└────────────────────────────────────────────────────────────────────────────┘
         ▲                            ▲                           ▲
         │                            │                           │
┌────────┴───────┐           ┌────────┴───────┐         ┌────────┴───────┐
│  JobSource ABC │           │  LLMProvider   │         │   Sender       │
│  (6 impls)     │           │  ABC (2 impls) │         │   Browser      │
└────────────────┘           └────────────────┘         └────────────────┘
```

### Module contracts (pseudo-Python)

```python
# sources/base.py
class JobSource(ABC):
    name: str   # e.g., "bundesagentur"
    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]: ...

# llm/base.py
class LLMProvider(ABC):
    def rank(self, job: Job, cv: str, filters: Filters) -> RankResult: ...
    def tailor(self, job: Job, cv: str, language: Literal["en", "de"]) -> str: ...

# repositories/job_repository.py
class JobRepository:
    def save_many(self, jobs: Iterable[Job]) -> int: ...   # returns inserted count
    def shortlisted(self, limit: int = 20) -> list[Job]: ...
    def get(self, job_id: str) -> Job: ...

# sender.py
class Sender:
    def send(self, application: Application, cv_path: Path) -> None: ...

# browser.py
class Browser:
    def open(self, url: str) -> None: ...
```

---

## 6. Implementation order (red → green → refactor, in this sequence)

Each step is "spec first, run failing, then code." No skipping ahead.

1. **Project scaffold**: `pyproject.toml`, `ruff` + `mypy --strict`
   config, empty `jobhunt/` package, empty `tests/` tree, local pre-commit
   script `bin/pre-commit-check.sh`, **GitHub Actions workflow
   `.github/workflows/ci.yml`** (see §13). Both must run cleanly on an
   empty repo.
2. **Models** (`models.py`): `RawPosting`, `Job`, `Application`,
   `RankResult`, `Filters`. Tests cover `Job.dedupe_hash()` first.
3. **DB + repositories**: `db.py` schema, `JobRepository`,
   `ApplicationRepository`. Integration test against real SQLite first.
4. **HTTP client factory** (`sources/_http.py`): timeout, single retry,
   user-agent. Unit tested with `respx`.
5. **Source adapters** in this order (pick one, ship it green, then next):
   1. `BundesagenturSource` (no auth — easiest path to a green flow)
   2. `ArbeitnowSource`
   3. `RemotiveSource`
   4. `WeWorkRemotelySource` (RSS — different parser path)
   5. `AdzunaSource` (auth)
   6. `JoobleSource` (auth)
   - Each ships with a captured fixture in `tests/fixtures/`. Each must
     pass `test_source_contract.py`.
6. **LLM providers**:
   1. `AnthropicProvider` first (default), implements `rank()`, `tailor()`,
      and `extract_profile()`.
   2. `OpenAIProvider` second, same three methods.
   3. Both must pass `test_provider_contract.py` (covering all three
      methods) before either is considered done.
7. **Ranker**: applies hard filters first (salary, location, language),
   then calls `LLMProvider.rank()` only on survivors. Test the cost-
   saving short-circuit explicitly.
8. **Tailor**: language detection from posting, picks template,
   calls `LLMProvider.tailor()`.
9. **CV pipeline**: `cv/reader.py` (PDF → text) and `cv/profile_seeder.py`
   (text → `ProfileDraft` via `LLMProvider.extract_profile()`). Unit
   tested with a checked-in PDF fixture and a fake LLM provider.
10. **Sender + Browser**: SMTP via stdlib `smtplib` + `email.message`.
    Sender unit-tested against `aiosmtpd` in-process server. Browser
    unit-tested by injecting a fake `webbrowser.open` callable.
11. **Services**: `FetchService`, `ReviewService`, `ApplyService` —
    constructor-DI'd, fully unit-tested with fakes.
12. **CLI** (`cli.py`): Typer commands wire the services from
    `wiring.py`. Smoke-tested with `CliRunner`.
13. **`jobhunt init`**: interactive setup. Reads `CV_PATH` → runs
    `ProfileSeeder` → writes `[filters]` defaults into `config.toml` →
    prompts the user to confirm/edit → writes `.env`. Tested by piping
    fake stdin through `CliRunner` with a fake `LLMProvider`.
14. **End-to-end integration test**: real SQLite, fake HTTP for all
    sources, fake LLM, fake SMTP — drives the full
    `fetch → review → send` flow and asserts DB state.

---

## 7. Configuration

### `.env.example`
```
# LLM provider — pick one
LLM_PROVIDER=anthropic                      # or "openai"
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_RANK=claude-haiku-4-5
ANTHROPIC_MODEL_TAILOR=claude-sonnet-4-6
OPENAI_API_KEY=sk-...
OPENAI_MODEL_RANK=gpt-4o-mini
OPENAI_MODEL_TAILOR=gpt-4o

# Source credentials (optional — sources without keys are skipped)
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
JOOBLE_API_KEY=

# SMTP for sending applications
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=you@example.com

# Owner profile
CV_PATH=/app/var/cv/cv.pdf
OWNER_NAME=Your Name
OWNER_EMAIL=you@example.com

# Filters
MIN_SALARY_EUR=90000
ALLOWED_LOCATIONS=remote,karlsruhe,frankfurt,munich,eu-remote
LANGUAGE_PREFERENCE=en
LANGUAGE_FALLBACK=de
SENIORITY=senior,lead,staff,principal
STACK_MUST_HAVES=php,symfony,python
```

### `config.toml` (filters + active sources; written by `jobhunt init`)

The `[filters]` block below is an **illustrative example**. `jobhunt init`
populates it by parsing `CV_PATH` through `LLMProvider.extract_profile()`,
so the actual values depend on the CV you provide. The user can edit any
field freely; nothing in the source tree references these values directly.

```toml
[filters]
min_salary_eur = 90000
allowed_locations = ["remote", "karlsruhe", "frankfurt", "munich", "eu-remote"]
language_preference = "en"
language_fallback = "de"
seniority = ["senior", "lead", "staff", "principal"]
stack_must_haves = ["php", "symfony", "python"]
shortlist_size = 20

# Active source set — names must exist in sources.REGISTRY.
# `jobhunt init` writes this default; user edits the list to enable/disable.
# A source whose required env vars are missing is skipped with a warning.
[sources]
enabled = [
    "bundesagentur",
    "arbeitnow",
    "adzuna",
    "jooble",
    "remotive",
    "weworkremotely",
]
```

---

## 8. CLI surface

```
jobhunt init                # one-time interactive setup
jobhunt fetch               # pull → dedupe → rank → mark top 20 shortlisted
jobhunt review              # interactive walk-through of shortlist
jobhunt send                # send approved (email) / open browser (URL only)
jobhunt status              # summary of pending / approved / sent / manual
jobhunt                     # alias for `fetch && review && send`
```

Interactive review keys: `a` approve · `r` reject · `s` skip · `v` view
full ad · `l` letter preview · `q` quit & save state.

---

## 9. Acceptance gate

A deliverable is accepted when:

1. Every method-specific TDD checkpoint in §4.1 is green.
2. The Liskov contract tests
   (`test_provider_contract.py`, `test_source_contract.py`) are green
   for **every** registered provider and source.
3. `bin/pre-commit-check.sh` passes locally **and** the GitHub Actions
   workflow `.github/workflows/ci.yml` is green on the pushed commit:
   - `ruff check .` clean.
   - `ruff format --check .` clean.
   - `mypy --strict jobhunt` clean (zero `type: ignore`).
   - `pytest tests/unit -q` green.
   - `pytest tests/integration -q` green.
   - Coverage ≥ 90 % on `jobhunt/` (excluding `cli.py`).
4. End-to-end integration test (§6 step 14) green.
5. `jobhunt fetch` against real Bundesagentur API on a clean DB returns
   ≥ 20 ranked postings within 60 seconds.
6. `jobhunt review` lets the owner approve at least one entry, and
   `jobhunt send` either sends one real email (if a contact email is
   present) or opens one apply URL.
7. No deprecated code, no commented-out blocks, no `noqa`, no
   `type: ignore`.

---

## 10. Continuous integration (GitHub Actions)

Lives at `.github/workflows/ci.yml`. **Triggers on every push** (any branch)
and on pull requests targeting `main`. CI's only job is to invoke
`bin/pre-commit-check.sh` — the **same** script developers run locally.
The workflow contains no `uv`, `ruff`, `mypy`, or `pytest` invocations of
its own; the script (running inside the Docker container it builds) owns
the gate.

### `bin/pre-commit-check.sh` (single entry point)

Runs on the host. Builds the dev image via `docker compose`, then
executes every gate step inside one container:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose build jobhunt
docker compose run --rm jobhunt bash -lc '
  set -euo pipefail
  uv sync --frozen --all-extras
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy --strict jobhunt
  uv run pytest tests/unit -q \
    --cov=jobhunt --cov-report=term-missing --cov-fail-under=90
  uv run pytest tests/integration -q
'
echo "✅ pre-commit-check passed"
```

### Workflow

```yaml
name: ci

on:
  push:
  pull_request:
    branches: [main]

jobs:
  gate:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      - name: Run pre-commit gate (in Docker)
        run: ./bin/pre-commit-check.sh
        env:
          # Integration tests must run with NO real network keys —
          # everything is faked in-process. CI deliberately blanks these
          # so a leaked key can't accidentally hit a real API.
          ANTHROPIC_API_KEY: ""
          OPENAI_API_KEY: ""
          ADZUNA_APP_ID: ""
          ADZUNA_APP_KEY: ""
          JOOBLE_API_KEY: ""
          SMTP_HOST: ""
```

(Ubuntu runners ship with Docker pre-installed; no setup step needed.)

### Rules

- **One script, one truth.** The pre-commit script is the *only* place
  that orchestrates the gate. CI does not re-encode the same steps in
  YAML. If a developer's `./bin/pre-commit-check.sh` is green, CI must be
  green on the same commit, modulo network flakes.
- **Docker is the only runtime.** No native `uv` / `pytest` invocations
  exist anywhere — not in CI, not in the script. Anything that needs to
  run code goes through `docker compose run --rm jobhunt …`.
- **No live-network integration tests in CI.** Every external call
  (HTTP source, LLM, SMTP) is faked in-process. The CI step that hits
  the real Bundesagentur API in §9.5 is **manual / local-only** — it is
  never part of the CI workflow.
- **Coverage gate is enforced inside the script** via
  `--cov-fail-under=90`. The exclude list (`cli.py`, `wiring.py`) lives
  in `pyproject.toml` under `[tool.coverage.run]`.
- **Cache discipline.** Docker layer caching (Dockerfile ordering: copy
  `pyproject.toml` + `uv.lock` first, run `uv sync`, then copy source) is
  the only cache. No manual pip / mypy / pytest caches.
- **Workflow failures block merge.** `main` is not protected (personal
  repo), but the owner's rule for himself is: red CI = revert, never
  "fix forward on main."
- **Adding a gate step is a code change like any other.** It goes
  through the same TDD discipline — if the step asserts something, that
  assertion is a test, and the test must fail meaningfully before the
  step is wired up.

---

## 11. Out of scope (explicitly deferred)

- LinkedIn / StepStone / XING scraping (ToS).
- Reply-tracking (parsing recruiter replies into `responses` table).
- Web UI / daemon / cron.
- Multi-user / SaaS-ification.
- Postgres backend.
- Salary parsing from free-text descriptions (v1 uses only structured
  salary fields when the source provides them; descriptions are passed
  to the LLM ranker for soft signals).
- Auto-translate of postings (the LLM tailor handles language by
  picking the matching cover-letter template; no separate translation
  step).

---

## 12. Risks and mitigations

| Risk                                                            | Mitigation                                                                                              |
|-----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| LLM cost runs away on a 200-posting fetch                       | Hard filters (salary, location, language) gate posts BEFORE any LLM call. Cheap model for ranking, strong only for tailoring approved letters. Anthropic prompt cache on the CV. |
| Source API silently changes JSON shape                          | Each source has a captured fixture; contract test asserts required fields. CI fails the day the shape drifts. |
| SMTP send goes to spam                                          | Use the owner's real Gmail SMTP with proper headers (`From`, `Reply-To`, `Message-ID`). No bulk sending — max 10/day cap in `apply_service.py`. |
| Owner approves the wrong posting and a cover letter goes out    | `apply` always shows the rendered letter + recipient + subject and waits for explicit `s` (send) before SMTP. No silent send.                |
| Anthropic ↔ OpenAI behavioural drift breaks Liskov              | Shared contract test in `test_provider_contract.py` runs against both on every CI build. New provider can't merge without passing it.        |
| Bundesagentur API blocks the IP                                 | Polite UA, one retry, hard cap of 200 results per fetch run. If blocked, the adapter fails loudly — no silent skip.                          |
| LLM hallucinates wrong filter values from CV                    | `jobhunt init` shows the seeded `[filters]` to the user and waits for explicit confirmation/edit before writing `config.toml`. `--reseed` re-runs the same flow without losing other config.   |
| CI accidentally talks to a live API                             | CI workflow blanks all `*_API_KEY` / `SMTP_*` env vars in the integration step. Every external call is faked in-process. No live-network test runs in CI; the §9.5 real-Bundesagentur smoke is local-only. |

---

## 13. References

- The engineering bar (TDD-first, SOLID, DRY, DI, Clean Code, no
  over-engineering, drop deprecated) is documented inline in §4.
- Owner CV (used by ranker + tailor): user-provided at `CV_PATH` (default
  `/app/var/cv/cv.pdf`, bind-mounted from the host).
- Cover-letter templates: `LLMProvider.tailor()` generates per-posting
  letters; the candidate's writing style is learned from the CV by
  `LLMProvider.extract_profile()`.
