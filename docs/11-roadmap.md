# 11. Delivery Roadmap

MVP path (recommended): **discovery → matching → tailored resume → autofill →
user verification → submit**, with one ATS adapter at a time rather than all at once.

| Phase | Scope | State |
| --- | --- | --- |
| 1 | Auth, profile, resume upload + parsing, database + migrations, dashboard | **Implemented** |
| 2 | Job ingestion, normalization, dedupe, matching engine, preferences | **Implemented** |
| 3 | AI resume tailoring, cover letters, application question engine | **Implemented** |
| 4 | Playwright engine, ATS detection, Greenhouse / Lever / Ashby adapters | **Implemented** |
| 5 | Workday, iCIMS, SmartRecruiters, generic fallback adapter | **Implemented** |
| 6 | Application queue, automation dashboard, human intervention | **Implemented** |
| 7 | Notifications, analytics, billing | **Implemented** |
| 8 | Production deployment, monitoring, security hardening | **Implemented** (Terraform skeleton) |

Gate between phases: `pytest -q` green, `npm run typecheck` clean, migrations applied
from scratch on an empty database.

## What phases 7 and 8 added

| Area | Where |
| --- | --- |
| In-app + e-mail notifications | `apps/api/.../services/notification_service.py`, gated per user by `notification_preferences` |
| Analytics API and charts | `apps/api/.../services/analytics_service.py`, `GET /analytics`, `apps/web/app/(app)/analytics` |
| Plan limits and billing seam | `packages/shared/jobapply_shared/billing.py`, `GET/POST /billing/*`, `apps/web/app/(app)/billing` |
| Prometheus metrics | `packages/shared/jobapply_shared/metrics.py`, `GET /api/v1/metrics` (counters and latencies only) |
| Error reporting and tracing | `packages/shared/jobapply_shared/observability.py` — no-ops until configured, PII off, `redact` as the scrubber |
| Worker liveness | `worker.heartbeat` periodic task, surfaced by `GET /health/ready` |
| Admin console | `apps/api/.../routers/admin.py`, `apps/web/app/(app)/admin` (role-gated) |
| Deployment skeleton | `infrastructure/docker/*`, `infrastructure/terraform/` |
| Credential vault | `apps/api/.../services/credential_service.py`, `/credentials`, the vault panel in Settings, and the worker's one-shot sign-in step |
| Guided onboarding | `apps/web/app/(app)/onboarding`, driven by the per-section state `GET /profile/onboarding` now returns |

## Not built yet

These are named in the specification and deliberately not implemented; nothing
in the codebase pretends otherwise.

| Item | Status |
| --- | --- |
| Inbox parsing of employer e-mail | Optional in the specification; not started. Application outcomes are recorded from the run itself and from manual status updates instead |
