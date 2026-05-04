# Sub-sprint 06 — Delivery (Sender + Browser) + Services

**Status:** PLANNED
**Parent:** [`sprint-01-jobhunt-mvp.md`](sprint-01-jobhunt-mvp.md)
**Depends on:** sub-sprints 03 (sources) and 05 (ranker / tailor)
**Unblocks:** sub-sprint 07 (CLI wires services together)

---

## 1. Goal

Land the two delivery primitives (`Sender` for SMTP, `Browser` for apply
URLs) and the three orchestrating services (`FetchService`,
`ReviewService`, `ApplyService`). Services are constructor-DI'd and
unaware of any concrete adapter, provider, or repository — they receive
ABCs only. After this sub-sprint, the entire flow runs end-to-end **in
tests** (sub-sprint 07 wires it to a real CLI).

## 2. Deliverables

- `jobhunt/sender.py` — `Sender`:
  ```python
  class Sender:
      def __init__(self, smtp_config: SmtpConfig) -> None: ...
      def send(self, application: Application, cv_path: Path) -> None: ...
  ```
  Builds an RFC 5322 message via stdlib `email.message.EmailMessage`,
  attaches CV PDF, sends via stdlib `smtplib.SMTP_SSL`. Sets `From`,
  `Reply-To`, `Message-ID`. Raises `SmtpSendError` on 5xx.
- `jobhunt/browser.py` — `Browser`:
  ```python
  class Browser:
      def __init__(self, opener: Callable[[str], bool] = webbrowser.open) -> None: ...
      def open(self, url: str) -> None: ...
  ```
  Tiny wrapper around `webbrowser.open` with the opener injected for
  testability.
- `jobhunt/services/fetch_service.py` — `FetchService`:
  ```python
  class FetchService:
      def __init__(self, sources: list[JobSource], jobs: JobRepository, ranker: Ranker, shortlist_size: int) -> None: ...
      def run(self) -> FetchReport: ...
  ```
  For each source: `fetch()` → normalise to `Job` → `jobs.save_many()`
  (dedupe). Then iterate newly-saved jobs through `ranker.score_many()`,
  persist scores, mark top-N as shortlisted.
- `jobhunt/services/review_service.py` — `ReviewService`:
  ```python
  class ReviewService:
      def __init__(self, jobs: JobRepository, apps: ApplicationRepository, tailor: Tailor) -> None: ...
      def next(self) -> Iterator[ReviewItem]: ...
      def record(self, job_id: str, decision: Decision) -> None: ...
  ```
  Yields one shortlisted item at a time, persists the owner's decision
  before yielding the next. Generates the cover letter at approval time
  (not before — saves LLM tokens on rejected/skipped items).
- `jobhunt/services/apply_service.py` — `ApplyService`:
  ```python
  class ApplyService:
      def __init__(self, apps: ApplicationRepository, sender: Sender, browser: Browser, cv_path: Path, daily_cap: int = 10) -> None: ...
      def apply_via_email(self, app: Application) -> None: ...
      def apply_via_browser(self, app: Application) -> None: ...
      def run(self) -> ApplyReport: ...
  ```
  No flag arguments — two distinct methods per parent §4.6. `run()`
  inspects each approved application and dispatches to the right method.
  Daily cap enforced by counting `sent_at` rows in the last 24 h.

## 3. TDD checkpoints

| Method                                | Spec written first                                                                       |
|---------------------------------------|------------------------------------------------------------------------------------------|
| `Sender.send()`                       | builds message with correct headers (asserted by parsing the in-process `aiosmtpd` capture); attaches CV; raises `SmtpSendError` on simulated 5xx |
| `Browser.open()`                      | calls injected opener exactly once with the URL; raises `BrowserOpenError` if opener returns `False` |
| `FetchService.run()` per-source isolation | one source raising does not abort the run — other sources still fetch and persist; the failure is recorded in `FetchReport.failures` |
| `FetchService.run()` shortlisting     | after fetch + score, exactly `shortlist_size` jobs are marked `shortlisted=1`, ordered by score |
| `ReviewService.next()`                | yields shortlisted items in score order; second iteration after `record()` skips the just-recorded job |
| `ReviewService.record()` with `approved` | triggers `tailor.write(job)`; cover letter persisted on the `Application` row before `next()` yields again |
| `ApplyService.apply_via_email()`      | calls `sender.send()`; sets `delivery="email"`, `sent_at=now`                            |
| `ApplyService.apply_via_browser()`    | calls `browser.open()`; sets `delivery="browser"`, `sent_at=now`, marks `manual=True`    |
| `ApplyService.run()` daily cap        | when 10 emails are already sent in the last 24 h, the 11th approved-with-email is **left pending** with a documented `ApplyReport.skipped_reason="daily_cap"` (no exception, no silent send) |

## 4. Acceptance

1. All TDD checkpoints green.
2. `Sender` integration test runs against a real in-process `aiosmtpd`
   server and inspects the captured message.
3. Services have **zero** imports from `jobhunt.sources.bundesagentur`,
   `jobhunt.llm.anthropic_provider`, etc. (only ABCs). CI grep step
   enforces this.
4. Coverage on `jobhunt/sender.py`, `jobhunt/browser.py`,
   `jobhunt/services/` ≥ 90 %.
5. `apply_service.py` does not contain a flag argument anywhere — two
   methods, no `if send_email: …` branch.

## 5. Out of scope

- CLI wiring — sub-sprint 07.
- The `wiring.py` container — sub-sprint 07.
- Any retry / queueing for failed sends. A failure is recorded; the
  owner re-runs `jobhunt send`.
