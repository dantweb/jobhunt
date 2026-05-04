# Sub-sprint 01 — Scaffold + CI (Docker-first)

**Status:** PLANNED
**Parent:** [`sprint-01-jobhunt-mvp.md`](sprint-01-jobhunt-mvp.md)
**Depends on:** —
**Unblocks:** sub-sprint 02

---

## 1. Goal

Stand up an empty, CI-green Python project where **the host machine
never runs Python directly**. Docker is the only runtime — for
developers, for the pre-commit gate, and for GitHub Actions CI. A single
shell script (`bin/pre-commit-check.sh`) is the one and only orchestrator
of the lint/type/test gate, and it executes everything inside a container
built from a committed `Dockerfile`.

The full quality bar is wired up before any production code lands:
`ruff` lint+format, `mypy --strict`, `pytest` with coverage gate ≥ 90 %.
Nothing under `jobhunt/` is implemented yet — this sub-sprint exists so
that on day one of real work, "red CI" has at most one suspect file.

## 2. Deliverables

### Docker layer (the runtime)

- `Dockerfile` — `python:3.11-slim` base, installs `uv` (binary copy
  from `ghcr.io/astral-sh/uv:latest`), declares `WORKDIR /app`, sets
  `UV_LINK_MODE=copy`. No source code is `COPY`d into the image —
  source is bind-mounted at runtime via compose, so the image rebuilds
  only when `Dockerfile` / `pyproject.toml` / `uv.lock` change.
- `docker-compose.yml` — single service `jobhunt`:
  - `build: .`
  - bind mount `.:/app`
  - named volume for the `uv` cache (`jobhunt-uv-cache:/root/.cache/uv`)
    so `uv sync` is fast across runs
  - `working_dir: /app`
  - `env_file: .env` (optional — present in dev, absent in CI)
- `.dockerignore` — excludes `.venv`, `.git`, `.pytest_cache`,
  `.mypy_cache`, `.ruff_cache`, `htmlcov`, `*.db`, `*.sqlite*`,
  `docs/`, etc. so the build context stays small.

### Python project (no source yet — the gate is the deliverable)

- `pyproject.toml` — uv-managed, Python 3.11+, declares:
  - runtime deps placeholders only (no `anthropic`, `openai`, etc. yet —
    those land with their owning sub-sprint)
  - dev deps: `ruff`, `mypy`, `pytest`, `pytest-cov`, `respx`,
    `aiosmtpd`, `pdfplumber` (each justified by a future sub-sprint)
  - `[tool.ruff]`, `[tool.ruff.format]`, `[tool.mypy]` (`strict = true`),
    `[tool.pytest.ini_options]`, `[tool.coverage.run]` (excludes
    `jobhunt/cli.py` and `jobhunt/wiring.py`)
- `uv.lock` — committed; reproducible builds.
- `jobhunt/__init__.py` — empty package marker.
- `tests/__init__.py`, `tests/unit/__init__.py`,
  `tests/integration/__init__.py` — empty.
- `tests/test_smoke.py` — single test asserting `import jobhunt`. Exists
  so coverage tooling has *something* to measure on day one.
- `.env.example` — header comment + every env var the parent sprint §7
  references, all blank.
- `.gitignore` — `.env`, `.venv`, `__pycache__`, `.pytest_cache`,
  `.mypy_cache`, `.ruff_cache`, `htmlcov`, `*.db`, `*.sqlite*`.
- `README.md` — minimum: project summary (1 paragraph), "this is in
  planning, see `docs/dev_log/20260429/`", and the **Docker-first**
  quickstart:
  ```
  docker compose build
  ./bin/pre-commit-check.sh
  ```
  No `uv sync` instruction, no `pip install`. The host needs only Docker.

### The single entry point

- `bin/pre-commit-check.sh` — executable. Runs the full gate **inside
  the container** in one `docker compose run` invocation (one container
  lifecycle, one bind mount, one cache hit on `uv`):
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

### CI workflow

- `.github/workflows/ci.yml` — triggers on every push and on PRs to
  `main`. **One job, one step:** invoke `./bin/pre-commit-check.sh`.
  The workflow contains zero `uv`, `ruff`, `mypy`, `pytest` references
  of its own. Env block blanks every `*_API_KEY` / `SMTP_*` variable per
  parent §10.

## 3. TDD checkpoints

This sub-sprint is **about the gate, not about features**. There is one
real test plus several gate-level assertions:

| Method / artefact            | Spec written first                                                      |
|------------------------------|-------------------------------------------------------------------------|
| `tests/test_smoke.py`        | `import jobhunt` succeeds; this is what proves the package is on path inside the container |
| Image build                  | `docker compose build jobhunt` succeeds on a clean machine in < 5 min on the first build |
| `bin/pre-commit-check.sh` runs entirely in-container | a `which python` and `which uv` invoked from the host **fails** (or returns the host's, not the container's); no host-level Python execution exists in the script — verified by grep against `bin/pre-commit-check.sh` for `^uv ` / `^python ` / `^pytest ` (none allowed) |
| `bin/pre-commit-check.sh` gate steps | each gate (ruff / format / mypy / unit / coverage / integration) is verified to fail loudly when broken on purpose: deliberately introduce one violation per gate, watch the script fail with the right exit code, then revert (do this once locally; do not commit the violation) |
| `.github/workflows/ci.yml`   | a deliberately-broken commit on a throwaway branch goes red on the matching gate before this sub-sprint is closed (then revert) |

## 4. Acceptance

1. `./bin/pre-commit-check.sh` on a fresh clone, with **only** Docker
   installed on the host, is green from a cold start (no `uv`, no
   `python3`, no `pyenv` on PATH).
2. The GitHub Actions workflow on the latest commit of this sub-sprint
   is green, running the same script.
3. Inside the container, `uv run pytest --cov=jobhunt --cov-report=term-missing`
   reports coverage on `jobhunt/__init__.py` only (one trivial file).
   The `--cov-fail-under=90` gate must still pass — adjust the exclude
   list in `pyproject.toml` if needed so this is honest, not gamed.
4. Inside the container, `uv run mypy --strict jobhunt` is clean with
   **zero** `# type: ignore`.
5. No `# noqa`, no commented-out code, no `# TODO` markers anywhere.
6. **Grep guard:** `bin/pre-commit-check.sh` and
   `.github/workflows/ci.yml` together contain **zero** lines matching
   `^\s*(uv |python |pytest |ruff |mypy )` outside the
   `docker compose run` body. Enforced by a one-line `grep` test inside
   the script itself, run as the very first gate step.

## 5. Out of scope

- Any production module under `jobhunt/` beyond `__init__.py`.
- Any source adapter, LLM provider, repository, or service.
- Branch-protection rules on GitHub (this is a personal repo; CI is
  advisory at the workflow level only).
- A separate `Dockerfile.prod` / multi-stage production image — v1 is
  a CLI run by the owner; the dev image is the only image. If we ever
  ship to a server, that's a future sub-sprint.
