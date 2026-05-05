#!/usr/bin/env bash
set -euo pipefail

# Single entry point for the lint/type/test gate.
# Runs every step inside the Docker container so the host needs only Docker.
# Used by developers locally and by GitHub Actions CI — the same script.

cd "$(dirname "$0")/.."

# Grep guard — forbid bare uv / python / pytest / ruff / mypy / pip
# invocations at the *shell* level (column 0–3) outside any container body.
# The heredoc body inside `docker compose run … bash -lc '…'` is indented
# with 8+ spaces, so it does not match this pattern.
guarded_files=(bin/pre-commit-check.sh .github/workflows/ci.yml)
for file in "${guarded_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        continue
    fi
    violations="$(grep -nE '^[[:space:]]{0,3}(uv |python |pytest |ruff |mypy |pip )' "$file" || true)"
    if [[ -n "$violations" ]]; then
        echo "❌ Docker-only guard violated in $file:" >&2
        echo "$violations" >&2
        exit 1
    fi
done

docker compose build jobhunt

docker compose run --rm \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    -e ADZUNA_APP_ID="${ADZUNA_APP_ID:-}" \
    -e ADZUNA_APP_KEY="${ADZUNA_APP_KEY:-}" \
    -e JOOBLE_API_KEY="${JOOBLE_API_KEY:-}" \
    -e SMTP_HOST="${SMTP_HOST:-}" \
    jobhunt bash -lc '
        set -euo pipefail
        uv sync --all-extras
        uv run ruff check .
        uv run ruff format --check .
        uv run mypy --strict -p jobhunt
        uv run pytest tests -q \
            --cov=jobhunt --cov-report=term-missing --cov-fail-under=90
    '

echo "✅ pre-commit-check passed"
