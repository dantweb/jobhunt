# Sub-sprint 04 — LLM providers (Anthropic + OpenAI)

**Status:** PLANNED
**Parent:** [`sprint-01-jobhunt-mvp.md`](sprint-01-jobhunt-mvp.md)
**Depends on:** sub-sprint 02 (uses `Job`, `RankResult`, `Filters`,
`ProfileDraft`)
**Unblocks:** sub-sprint 05 (Ranker / Tailor / CV seeder)

---

## 1. Goal

Implement both LLM providers behind a single ABC, with a shared parametrised
contract test that proves Liskov substitutability across the three methods
the rest of the codebase will call. Anthropic ships first as the default
(prompt-cached on the CV); OpenAI follows. Neither provider knows anything
about filters, the DB, or the CLI — they format prompts, call SDKs, and
parse responses. That's it.

## 2. Deliverables

- `jobhunt/llm/base.py` — `LLMProvider` ABC, three methods:
  ```python
  class LLMProvider(ABC):
      def rank(self, job: Job, cv: str, filters: Filters) -> RankResult: ...
      def tailor(self, job: Job, cv: str, language: Literal["en", "de"]) -> str: ...
      def extract_profile(self, cv_text: str) -> ProfileDraft: ...
  ```
- `jobhunt/prompts/rank.py` — system + user templates for `rank()`. The
  user prompt embeds `Filters` so the model sees the same constraints
  the hard filter applied. Output schema enforced via JSON-mode /
  tool-use response shape; parsed into `RankResult`.
- `jobhunt/prompts/tailor.py` — two templates (`en`, `de`), seeded from
  the owner's cover-letter files (parent §13). Output is plain text,
  one letter per call.
- `jobhunt/prompts/profile.py` — single template that takes CV text and
  returns a `ProfileDraft` JSON. Defaults documented inline for fields
  the CV does not specify.
- `jobhunt/llm/anthropic_provider.py` — uses the `anthropic` SDK,
  enables prompt caching on the CV block (the CV is the largest
  invariant input across all three methods).
- `jobhunt/llm/openai_provider.py` — uses the `openai` SDK, structured
  outputs / JSON mode for `rank()` and `extract_profile()`.
- `jobhunt/llm/__init__.py` — small factory:
  `get_provider(name: Literal["anthropic", "openai"], config) -> LLMProvider`.
- `tests/unit/llm/test_provider_contract.py` — **the** Liskov gate.
  Parametrised over both providers via a fake transport. Asserts:
  - `rank()` returns `RankResult` with `0 ≤ score ≤ 100`, non-empty
    `reason`, `flags ⊆ ALLOWED_FLAGS`.
  - `tailor()` with `language="en"` returns text that does **not**
    contain Umlauts in the greeting; `language="de"` returns text
    **with** the German salutation form. (Coarse, but sufficient as a
    smoke check that the right template was picked.)
  - `extract_profile()` returns a `ProfileDraft` with all six fields
    populated (defaults applied where the CV is silent).
  - Errors raised for malformed responses use the same exception type
    in both providers (`LLMResponseError`).

## 3. TDD checkpoints

| Method                           | Spec written first                                                                       |
|----------------------------------|------------------------------------------------------------------------------------------|
| `AnthropicProvider.rank()`       | parses a known-good fake response into `RankResult`; mismatched score range → `LLMResponseError` |
| `AnthropicProvider.tailor()`     | EN template → English letter; DE template → German letter; provider does NOT decide language (parameter is authoritative) |
| `AnthropicProvider.extract_profile()` | known fixture CV text → known `ProfileDraft`; missing fields default per documented values |
| `AnthropicProvider` prompt cache | the CV block is sent with `cache_control={"type": "ephemeral"}` — verified by inspecting the request payload in the fake transport |
| `OpenAIProvider.*`               | identical contract assertions as the three above (parametrised contract test enforces this) |
| **Contract test** (both providers, all three methods) | every method's postconditions hold; no provider strengthens preconditions (e.g. neither requires CV length above the base contract's documented minimum) |

## 4. Acceptance

1. Both providers pass `test_provider_contract.py`. **No conditional
   skips per provider.**
2. Per-provider unit tests green against fake SDK transports — **no live
   API calls in any test**, including in CI (parent §10 blanks the keys).
3. Anthropic provider's outgoing request payload demonstrably uses
   prompt caching on the CV block.
4. Coverage on `jobhunt/llm/` and `jobhunt/prompts/` ≥ 90 %.
5. `mypy --strict` green, zero `# type: ignore` (provider SDKs ship type
   stubs; if a stub is genuinely missing, document the alternative in the
   PR description per parent §4.6).

## 5. Out of scope

- Filter logic — `Ranker` (sub-sprint 05) decides what to filter; the
  provider only scores.
- CV reading from disk — `cv/reader.py` (sub-sprint 05) hands the
  provider a string.
- Caching across runs (disk-level memoisation) — Anthropic's in-flight
  prompt cache is enough for v1.
