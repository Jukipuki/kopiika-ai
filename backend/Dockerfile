# Stage 1: Install dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Ensure virtualenv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# App version — passed in by CI from the repo-root VERSION file at build
# time (the file is outside this Dockerfile's build context, so it can't
# be COPY'd directly). app/core/version.py prefers this env var over its
# walk-up VERSION-file lookup.
ARG APP_VERSION=0.0.0+unknown
ENV APP_VERSION=$APP_VERSION

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["./entrypoint.sh"]
