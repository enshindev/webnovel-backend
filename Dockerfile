# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock .python-version README.md ./
COPY src/ ./src/
COPY apps/ ./apps/
COPY prompts/ ./prompts/
COPY evals/ ./evals/
COPY knowledge/ ./knowledge/
COPY config/ ./config/
COPY migrations/ ./migrations/
COPY alembic.ini ./

RUN uv sync --frozen --no-dev --extra export --extra library --extra ocr \
    && mkdir -p /app/data/exports /app/data/library

EXPOSE 8000

CMD ["webnovel", "serve", "--host", "0.0.0.0", "--port", "8000"]
