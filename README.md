# JobApply — AI job application automation, with a human in the loop

A production-oriented platform that finds relevant jobs, scores them against a verified
profile, tailors a resume from facts the user has approved, fills supported application
forms, and **stops and asks** whenever a human is genuinely required.

## The design choice that shapes everything

Ordinary application steps are fully automated. These are not:

| Situation | What happens |
| --- | --- |
| CAPTCHA | Run pauses, user is notified, user completes it in their own session |
| MFA / OTP | Run pauses, user supplies the code, automation continues; the code is never stored |
| Legal attestation | Never auto-answered — the user answers it themselves |
| Work authorization / sponsorship | Answered only from explicit profile fields, never inferred, never model-generated |
| Ambiguous or low-confidence question | Escalated for review with the automation's draft attached |
| Unsupported application flow | Escalated rather than guessed at |

The platform does not solve CAPTCHAs, bypass MFA, evade bot detection, or touch any
account the user has not authorized. Rate limits exist to protect the user's own
reputation, not to work around an employer's controls.

The second invariant: **nothing is invented**. Every statement that reaches an employer
traces back to a record the user supplied or approved. The `ResumeTruthLayer` rejects
unlisted technologies, inflated numbers ("8 years of AWS" against a profile that says
3), ungrounded prose, and any legally significant claim.

## Quick start

```bash
cp .env.example .env          # placeholders only — never commit real secrets
docker compose up --build     # web :3000  api :8000  postgres  redis  minio  mailpit
```

The API is at `http://localhost:8000` with interactive docs at `/docs`. It runs with
`AI_PROVIDER=mock` and local filesystem storage, so no cloud account or API key is
needed to develop against it.

Without Docker:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://jobapply:jobapply@localhost:5432/jobapply
alembic -c packages/database/alembic.ini upgrade head
uvicorn jobapply_api.main:app --reload
celery -A jobapply_workers.celery_app worker -Q default,resumes,notifications
cd apps/web && npm install && npm run dev
```

## Tests

```bash
pytest -q                     # unit + integration, no external services required
ruff check . && ruff format --check .
TEST_POSTGRES_URL=postgresql+psycopg://... pytest tests/integration/test_migrations.py
cd apps/web && npm run typecheck && npm run lint
```

Browser tests are opt-in (`-m browser`) and run a real Chromium against the local mock
ATS sites in `tests/mock_ats/` only:

```bash
pytest tests/browser -m browser          # needs Chromium; set BROWSER_EXECUTABLE_PATH to pin one
```

Submitting test applications to real employers is prohibited.

## Repository layout

```
apps/api        FastAPI edge + service layer          (jobapply_api)
apps/workers    Celery workers and schedule           (jobapply_workers)
apps/web        Next.js frontend
packages/shared settings, logging, security, storage, e-mail, text, rate limits
packages/database SQLAlchemy models + Alembic migrations
packages/ai     AIProvider abstraction, prompt registry, guardrails
packages/resume parsing, ResumeTruthLayer, tailoring contracts
packages/jobs   job sources, normalization, dedupe, matching
packages/browser Playwright engine and ATS adapters
infrastructure  Dockerfiles and Terraform skeleton
docs            architecture, ERD, interfaces, API contracts, security model
tests           unit / integration / browser + fixtures and mock ATS sites
```

## Status

| Phase | Scope | State |
| --- | --- | --- |
| 1 | Auth, profile, resume upload + parsing, database, dashboard | **Implemented and tested** |
| 2 | Job ingestion, normalization, dedupe, matching, preferences | **Implemented and tested** |
| 3 | Resume tailoring, cover letters, question engine, field mapping | **Implemented and tested** |
| 4–6 | Playwright engine, seven ATS adapters, queue, interventions | **Implemented and tested** |
| 7 | Notifications, analytics, billing | **Implemented and tested** — in-app + e-mail notifications, `/analytics` API and charts, plan limits with a Stripe adapter |
| 8 | Production deployment, monitoring, security hardening | **Implemented and tested** — Prometheus `/metrics`, worker heartbeats in readiness, Sentry/tracing hooks, admin console, Docker images; Terraform remains a skeleton |

See [`docs/11-roadmap.md`](docs/11-roadmap.md) for the full plan and
[`docs/01-architecture.md`](docs/01-architecture.md) for the architecture.

## Documentation

| Document | Contents |
| --- | --- |
| [`docs/01-architecture.md`](docs/01-architecture.md) | System diagram, request paths, module boundaries |
| [`docs/02-repository-structure.md`](docs/02-repository-structure.md) | Layout and dependency rules |
| [`docs/03-database-erd.md`](docs/03-database-erd.md) | ERD and per-table notes |
| [`docs/04-interfaces.md`](docs/04-interfaces.md) | `AIProvider`, `ApplicationAdapter`, storage, e-mail, billing |
| [`docs/05-api-contracts.md`](docs/05-api-contracts.md) | REST contracts, conventions, auth model |
| [`docs/06-workers.md`](docs/06-workers.md) | Queues, retry policy, schedule |
| [`docs/07-browser-automation.md`](docs/07-browser-automation.md) | Pipeline, ATS detection, safety rules |
| [`docs/08-ai-services.md`](docs/08-ai-services.md) | Prompt registry and guardrails |
| [`docs/09-security-model.md`](docs/09-security-model.md) | Identity, encryption, audit, abuse controls |
| [`docs/10-local-development.md`](docs/10-local-development.md) | Local stack and substitutes |
