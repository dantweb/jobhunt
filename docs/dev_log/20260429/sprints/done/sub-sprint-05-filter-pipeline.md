# Sub-sprint 05 — Ranker, Tailor, CV pipeline

**Status:** PLANNED
**Parent:** [`sprint-01-jobhunt-mvp.md`](sprint-01-jobhunt-mvp.md)
**Depends on:** sub-sprint 04 (consumes `LLMProvider`)
**Unblocks:** sub-sprint 06 (services need a working ranker)

---

## 1. Goal

Build the three policy modules that sit between the raw HTTP/LLM layers
and the user-facing flow: hard-filter ranking, language-aware cover-letter
tailoring, and CV → `ProfileDraft` seeding. All three depend only on the
ABCs from earlier sub-sprints, never on concrete provider classes.

## 2. Deliverables

- `jobhunt/ranker.py` — `Ranker`:
  ```python
  class Ranker:
      def __init__(self, llm: LLMProvider, filters: Filters, cv: str) -> None: ...
      def score(self, job: Job) -> RankResult | None: ...   # None ⇒ filtered out
      def score_many(self, jobs: Iterable[Job]) -> list[tuple[Job, RankResult]]: ...
  ```
  Hard filters are pluggable via `FilterRule` subclasses registered in
  the constructor (parent §4.2 O — Open/closed). Default rule set:
  `SalaryFloorRule`, `LocationAllowlistRule`, `LanguageRule`,
  `SeniorityRule`, `StackRule`. Each rule returns `Pass | Reject(reason)`.
  The LLM is only invoked on jobs that pass every rule.
- `jobhunt/tailor.py` — `Tailor`:
  ```python
  class Tailor:
      def __init__(self, llm: LLMProvider, cv: str, owner_preference: Literal["en", "de"]) -> None: ...
      def write(self, job: Job) -> str: ...
  ```
  Picks `en` when posting language is English, `de` when German. Mixed
  → owner preference. Calls `LLMProvider.tailor()` with the chosen
  language.
- `jobhunt/cv/reader.py` — `CvReader.read(path: Path) -> str`. Uses
  `pdfplumber`. Raises `MissingCvError` on missing file, `CvReadError`
  on unreadable PDF.
- `jobhunt/cv/profile_seeder.py` — `ProfileSeeder`:
  ```python
  class ProfileSeeder:
      def __init__(self, llm: LLMProvider, reader: CvReader) -> None: ...
      def seed(self, cv_path: Path) -> ProfileDraft: ...
  ```
  Reads the CV, calls `LLMProvider.extract_profile()`. The CLI's
  `jobhunt init` (sub-sprint 07) consumes this.

## 3. TDD checkpoints

| Method                                | Spec written first                                                                       |
|---------------------------------------|------------------------------------------------------------------------------------------|
| `SalaryFloorRule`                     | salary below floor → `Reject`; salary at or above floor → `Pass`; missing salary → `Pass` with flag `salary_unstated` |
| `LocationAllowlistRule`               | `remote` always passes; `karlsruhe` passes; `berlin` rejects (not in default list); case-insensitive |
| `LanguageRule`                        | English-only posting → `Pass`; "Deutsch C2 / Muttersprache" without English → `Reject`; bilingual → `Pass` |
| `Ranker.score()` short-circuit        | a job that fails the salary rule is `None`; `LLMProvider.rank()` is **never called** — verified by mock asserting zero invocations |
| `Ranker.score()` happy path           | a job that passes all rules calls the LLM exactly once and returns the LLM's `RankResult` unchanged |
| `Tailor.write()` language selection   | EN posting → `LLMProvider.tailor(..., language="en")`; DE → `"de"`; mixed → owner preference; verified via mock |
| `CvReader.read()`                     | known fixture PDF → expected text; missing path → `MissingCvError`; corrupt bytes → `CvReadError` |
| `ProfileSeeder.seed()`                | reads CV via injected `CvReader`, calls injected `LLMProvider.extract_profile()`; both calls verified; returns the LLM's `ProfileDraft` unchanged |

## 4. Acceptance

1. All TDD checkpoints green.
2. The cost-saving short-circuit is **explicitly tested**: the parametrised
   short-circuit test runs against every default `FilterRule`, asserting
   that a single rejection prevents any LLM call.
3. Coverage on `jobhunt/ranker.py`, `jobhunt/tailor.py`, `jobhunt/cv/`
   ≥ 90 %.
4. **Zero direct provider references** in any of these modules — they
   accept `LLMProvider` only. Verified by a CI grep step asserting that
   `anthropic_provider`, `openai_provider`, `AnthropicProvider`,
   `OpenAIProvider` appear only under `jobhunt/llm/` and `tests/`.
5. A checked-in PDF fixture exists at `tests/fixtures/cv_sample.pdf`
   (small, synthetic — not the owner's real CV).

## 5. Out of scope

- The interactive `jobhunt init` flow itself — that's sub-sprint 07.
  This sub-sprint only ships `ProfileSeeder` as a library function.
- Persisting `RankResult` to the DB — sub-sprint 06 owns that
  (`FetchService` writes scores after the ranker returns them).
- Translating postings or regenerating cover letters in a different
  language — out of scope per parent §10.
