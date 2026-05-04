# Sub-sprint 07 — CLI, wiring, `jobhunt init`, end-to-end test

**Status:** PLANNED
**Parent:** [`sprint-01-jobhunt-mvp.md`](sprint-01-jobhunt-mvp.md)
**Depends on:** sub-sprint 06 (and transitively all earlier ones)
**Unblocks:** **sprint 01 acceptance** (parent §9)

---

## 1. Goal

Stitch every prior sub-sprint's work into a usable CLI, with a single
wiring file, an interactive `jobhunt init` that bootstraps `[filters]`
from the CV, and one full end-to-end integration test that drives
`fetch → review → send` against a real SQLite DB and in-process fakes
for HTTP / LLM / SMTP / browser. After this sub-sprint, the parent
sprint's acceptance gate (§9) is checkable end-to-end.

## 2. Deliverables

- `jobhunt/wiring.py` — single source of construction:
  ```python
  def build_container(config: AppConfig) -> Container: ...
  ```
  Reads `config.toml`'s `[sources] enabled` + the `REGISTRY` to construct
  the `JobSource` list. Reads `LLM_PROVIDER` env to pick the provider.
  Wires every service constructor. **No service locator, no DI
  container library** — plain Python constructors.
- `jobhunt/config.py` — `AppConfig` (pydantic-settings):
  - reads `.env` for credentials + `LLM_PROVIDER` + paths
  - reads `config.toml` for `[filters]` and `[sources]`
  - exposes `Filters`, `SmtpConfig`, source enable list, etc., as
    typed attributes
- `jobhunt/cli.py` — Typer app with five commands:
  - `jobhunt init` — interactive setup (see §3 below)
  - `jobhunt fetch` — `FetchService.run()` + summary
  - `jobhunt review` — interactive review loop with keys
    `a/r/s/v/l/q`
  - `jobhunt send` — `ApplyService.run()` + summary
  - `jobhunt status` — counts of pending / approved / sent / manual
  - bare `jobhunt` — alias for `fetch && review && send`
  Each command is < 30 lines; all logic delegated to services.
- `tests/integration/test_end_to_end.py` — drives the full flow:
  real SQLite, fake HTTP for all 6 sources, fake LLM provider, fake
  SMTP server, fake browser opener. Asserts:
  1. After `fetch`, the DB has ≥ 1 shortlisted job.
  2. After `review` (scripted approve/reject decisions piped via
     `CliRunner`), the approved job has a cover letter persisted.
  3. After `send`, an email is captured by the in-process SMTP server
     OR the browser opener was called — and the application row's
     `sent_at` is set.

## 3. `jobhunt init` flow (interactive)

This is the only command with non-trivial UX:

1. Prompt for `CV_PATH` (default to env var if set).
2. Run `ProfileSeeder.seed(cv_path)` — print "reading CV…" then "asking
   the model to extract your profile…".
3. Display the resulting `ProfileDraft` field-by-field. For each field,
   prompt: `[Enter] keep, or type new value:`.
4. Once confirmed, write `config.toml` with the agreed `[filters]` block
   plus the default `[sources] enabled = […]`.
5. Prompt for `LLM_PROVIDER` (default `anthropic`), the matching
   API key, the SMTP credentials, the optional Adzuna / Jooble keys.
6. Write `.env`. Print "done — run `jobhunt` to start."

Re-run support: `jobhunt init --reseed` re-runs only steps 1–4
(regenerates `[filters]` from a possibly-updated CV) without touching
`.env` or `[sources]`.

## 4. TDD checkpoints

| Method / behaviour                         | Spec written first                                                                       |
|--------------------------------------------|------------------------------------------------------------------------------------------|
| `wiring.build_container()`                 | given a config with 3 enabled sources, builds 3 `JobSource` instances; missing API key for one source → that source is **skipped with a warning**, container still builds |
| `wiring.build_container()` — provider switch | `LLM_PROVIDER=openai` → `OpenAIProvider` instantiated, `AnthropicProvider` not imported (verified via `sys.modules`) |
| `cli.fetch` smoke                          | `CliRunner` invokes `fetch`; `FetchService.run` is called once with the wired collaborators; exit code 0 |
| `cli.review` interactive                   | scripted stdin `a\nr\ns\nq\n` produces 1 approval, 1 rejection, 1 skip, then exits cleanly; DB state matches |
| `cli.send` dispatch                        | `ApplyService.run()` called; output summarises sent / browser / skipped counts          |
| `cli.init` with stdin script               | piped answers produce a valid `config.toml` and `.env`; `ProfileSeeder` invoked exactly once with the CV path |
| `cli.init --reseed`                        | only `[filters]` block changes; `.env` untouched; `[sources]` untouched                  |
| **End-to-end** `test_end_to_end.py`        | real SQLite + fake HTTP + fake LLM + fake SMTP + fake browser drives the full `fetch → review → send` and asserts the three checkpoints in §2's deliverable list |

## 5. Acceptance

1. All TDD checkpoints green.
2. End-to-end integration test green.
3. `jobhunt fetch` against the **real** Bundesagentur API (run locally,
   not in CI) returns ≥ 20 ranked postings within 60 seconds — parent §9.5.
4. `jobhunt review` lets the owner approve at least one entry, and
   `jobhunt send` either sends one real email (if a contact email is
   present) or opens one apply URL — parent §9.6.
5. `cli.py` and `wiring.py` are excluded from the ≥ 90 % coverage gate
   (parent §4.1) — but every command has at least one `CliRunner`
   smoke test.
6. Every parent §9 acceptance bullet is now true.

## 6. Out of scope

- Anything in parent §10 ("Out of scope, explicitly deferred").
- Reading the real owner CV in CI — the integration test ships its own
  synthetic PDF fixture from sub-sprint 05.
