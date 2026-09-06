# syntax=docker/dockerfile:1
# The automation worker is a separate image: it carries Chromium, which the API and
# the other workers have no reason to ship.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/workers ./apps/workers

RUN pip install --upgrade pip && pip install -e ".[browser]"

CMD ["celery", "-A", "jobapply_workers.celery_app", "worker", \
     "-Q", "automation", "--concurrency=2", "--loglevel=INFO"]
