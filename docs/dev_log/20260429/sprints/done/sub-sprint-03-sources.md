# Sub-sprint 03 — HTTP client + 6 source adapters

**Status:** PLANNED
**Parent:** [`sprint-01-jobhunt-mvp.md`](sprint-01-jobhunt-mvp.md)
**Depends on:** sub-sprint 02 (uses `RawPosting`, `Job`)
**Unblocks:** sub-sprint 06 (services consume sources)

---

## 1. Goal

Ship the full ingestion side: a single shared HTTP client and the six
source adapters listed as default-enabled in the parent sprint §2. Every
adapter is a `JobSource` subclass that does **only** HTTP — no DB, no
score, no dedupe, no normalisation beyond `RawPosting`. A single
parametrised contract test runs against all six and any future adapter.

## 2. Deliverables

- `jobhunt/sources/_http.py` — one factory:
  `make_client(timeout=10, retries=1, user_agent=…) -> httpx.Client`.
  Single retry on 5xx only (no retry on 4xx, no retry on connection
  errors — fail loudly per parent §4.7).
- `jobhunt/sources/base.py` — `JobSource` ABC:
  ```python
  class JobSource(ABC):
      name: ClassVar[str]
      def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]: ...
  ```
- `jobhunt/sources/__init__.py` — exposes `REGISTRY: dict[str, type[JobSource]]`
  keyed by `name`. Every adapter file registers itself here.
- Six adapters, each with a captured fixture:
  - `bundesagentur.py` (no auth) + `tests/fixtures/bundesagentur_sample.json`
  - `arbeitnow.py` (no auth) + fixture
  - `remotive.py` (no auth) + fixture
  - `weworkremotely.py` (RSS — different parser path) + fixture
  - `adzuna.py` (free key — `MissingCredentialsError` raised BEFORE
    network call when key missing) + fixture
  - `jooble.py` (free key — same) + fixture
- `tests/unit/sources/test_source_contract.py` — parametrised over every
  entry in `REGISTRY`, asserts the §4.4 postconditions of the parent.

## 3. TDD checkpoints

| Method / behaviour                       | Spec written first                                                                       |
|------------------------------------------|------------------------------------------------------------------------------------------|
| `make_client()` retry policy             | one 503 → retried once → 200 OK passes; two 503 → raises (no second retry)               |
| `make_client()` timeout                  | response that exceeds the timeout raises `httpx.TimeoutException`                        |
| `BundesagenturSource.fetch()`            | happy path (1 page) + pagination (2 pages stitched) + 5xx retry behaviour                |
| `ArbeitnowSource.fetch()`                | happy path + empty result set + JSON shape change (extra unknown field tolerated)        |
| `AdzunaSource.fetch()` / `JoobleSource.fetch()` | missing API key → raises `MissingCredentialsError` BEFORE any network call — verified by `respx` asserting zero requests |
| `WeWorkRemotelySource.fetch()`           | RSS XML parses correctly; missing optional fields default to `None`, never absent        |
| `RemotiveSource.fetch()`                 | happy path + filters out non-EU postings if the source returns global results            |
| **Contract test** (parametrised over all 6) | every fetch returns `Iterable[RawPosting]`; every `RawPosting` has all 5 required fields populated; no required field is `None` |

## 4. Acceptance

1. All six adapters pass `test_source_contract.py`.
2. Per-adapter unit tests green; each uses `respx` against the captured
   fixture — **no live network calls**.
3. `MissingCredentialsError` is raised pre-network in the two
   credentialed adapters (asserted via `respx`'s zero-request guarantee).
4. `REGISTRY` contains exactly six entries; their `name` keys match the
   default list in the parent sprint §2 table.
5. Coverage on `jobhunt/sources/` ≥ 90 %.

## 5. Out of scope

- Any DB write. Adapters return iterables; persistence is the service's
  job (sub-sprint 06).
- Any score / filter / dedupe logic.
- Live-network smoke tests in CI. The §9.5 real-Bundesagentur smoke is
  local-only; CI integration step blanks all keys per parent §10.
