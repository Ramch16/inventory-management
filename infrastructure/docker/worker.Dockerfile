# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
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

RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

CMD ["celery", "-A", "jobapply_workers.celery_app", "worker", \
     "-Q", "default,discovery,matching,resumes,notifications", "--loglevel=INFO"]
