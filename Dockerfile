FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:/root/.local/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# Install happens at runtime — `bin/pre-commit-check.sh` runs
# `uv sync --all-extras` against the bind-mounted /app, populating both
# /opt/venv (named volume) and /root/.cache/uv (named volume) on first
# run. Subsequent runs reuse the cached venv → near-instant sync.
#
# Pre-installing here was unreliable: Docker does not always bootstrap
# named volumes from image contents, so /opt/venv would arrive empty at
# runtime and uv would think deps were already in place.

CMD ["bash"]
