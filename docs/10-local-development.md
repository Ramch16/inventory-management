# 10. Local Development

## Prerequisites
Docker + Docker Compose (v2). Python 3.11 and Node 20+ only if running outside Docker.

## Quick start
```bash
cp .env.example .env          # placeholders only; never commit real secrets
docker compose up --build     # web :3000  api :8000  postgres :5432  redis :6379
docker compose exec api alembic upgrade head
docker compose exec api python -m jobapply_api.cli seed-demo   # optional sample data
```

Services in `docker-compose.yml`: `frontend`, `backend`, `worker`, `beat`, `postgres`,
`redis`, `minio` (S3-compatible object storage), `mailpit` (SMTP sink).

## Running without Docker
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://... REDIS_URL=redis://localhost:6379/0
alembic -c packages/database/alembic.ini upgrade head
uvicorn jobapply_api.main:app --reload
celery -A jobapply_workers.celery_app worker -Q discovery,matching,resumes,notifications
cd apps/web && npm install && npm run dev
```

## Tests
```bash
pytest -q                      # unit + integration (SQLite for unit, PG for integration)
pytest tests/browser -q        # Playwright against tests/mock_ats only
cd apps/web && npm run lint && npm run typecheck && npm test
```

## Local substitutes
| Concern | Local implementation |
| --- | --- |
| LLM | `AI_PROVIDER=mock` → deterministic fixtures, no network, no key needed |
| Object storage | `STORAGE_BACKEND=local` (filesystem) or MinIO |
| E-mail | `EMAIL_BACKEND=console` (logged + `outbox` table) or Mailpit |
| Job sources | `SampleFeedSource` reading `tests/fixtures/jobs/*.json`, labelled as sample data |
| Billing | `NoopBillingService` |
