# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/workers ./apps/workers

RUN pip install --upgrade pip && pip install -e .

# The storage volume is mounted here. The directory has to exist in the image and be
# owned by the runtime user: Docker creates a missing mountpoint as root, and the
# unprivileged process below then cannot write an uploaded resume into it.
RUN mkdir -p /app/.storage

# The API runs as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "jobapply_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
