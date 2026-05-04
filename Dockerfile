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

# Pre-resolve and pre-fetch dependencies into the uv cache so subsequent
# `uv sync` calls inside the bind-mounted /app are near-instant. We only
# copy the manifest files here — the actual source tree comes in via the
# compose bind mount at runtime, so the editable install always sees the
# real, full package layout (including subpackages like jobhunt/cv/).
COPY pyproject.toml uv.lock* README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-extras --no-install-project --frozen 2>/dev/null \
    || uv sync --all-extras --no-install-project

CMD ["bash"]
