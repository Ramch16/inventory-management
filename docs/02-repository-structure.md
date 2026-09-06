# 2. Repository Structure

```
.
├── apps
│   ├── api                    # FastAPI edge + service layer  (package: jobapply_api)
│   │   └── jobapply_api
│   │       ├── main.py                 # app factory, middleware, health
│   │       ├── deps.py                 # DI: db session, current user, rbac
│   │       ├── errors.py               # problem+json error envelope
│   │       ├── routers/                # http only, no business logic
│   │       │   ├── auth.py  profile.py  resumes.py  jobs.py
│   │       │   ├── applications.py  interventions.py  analytics.py
│   │       │   ├── notifications.py  settings.py  admin.py
│   │       ├── schemas/                # Pydantic request/response models
│   │       └── services/               # business logic, transaction owners
│   ├── workers                # Celery app + tasks       (package: jobapply_workers)
│   │   └── jobapply_workers
│   │       ├── celery_app.py  beat.py
│   │       └── tasks/ discovery.py matching.py resumes.py applications.py email.py
│   └── web                    # Next.js 15 App Router + TS + Tailwind + shadcn/ui
│       ├── app/(auth)/login|register
│       ├── app/(app)/dashboard|profile|resume|jobs|applications|interventions|
│       │            settings|billing|analytics|onboarding
│       ├── app/admin/…
│       ├── components/  hooks/  lib/api/  lib/types/
│       └── ...
├── packages
│   ├── shared    (jobapply_shared)   config, structured logging, crypto, ids, enums,
│   │                                 rate limiting, redaction, result types
│   ├── database  (jobapply_db)       SQLAlchemy models, session, repositories,
│   │                                 alembic/ migrations
│   ├── ai        (jobapply_ai)       AIProvider, provider impls, prompt registry,
│   │                                 JSON-schema validation, guardrails
│   ├── resume    (jobapply_resume)   parsers, ResumeTruthLayer, tailoring,
│   │                                 renderers (DOCX/PDF), quality scoring
│   ├── jobs      (jobapply_jobs)     JobSource adapters, normalizer, dedupe,
│   │                                 JobMatchingService
│   └── browser   (jobapply_browser)  BrowserManager, ATSDetector, FormAnalyzer,
│                                     AnswerResolver, FormFiller, UploadManager,
│                                     SubmissionManager, VerificationHandler,
│                                     adapters/ (greenhouse, lever, ashby, workday,
│                                     icims, smartrecruiters, generic)
├── infrastructure
│   ├── docker    Dockerfiles (api, worker, web, automation), entrypoints
│   └── terraform AWS skeleton (vpc, rds, elasticache, s3, ecs, secrets)
├── tests
│   ├── unit/  integration/  browser/  fixtures/  mock_ats/   # local mock ATS sites
├── docs
├── docker-compose.yml
├── .env.example
└── pyproject.toml
```

## Module independence rules

* `packages/*` never import from `apps/*`.
* `apps/api` and `apps/workers` may import any `packages/*`.
* `apps/api/jobapply_api/services` is the shared service layer, not an HTTP detail:
  `apps/workers` imports it so a scheduled run and a user-initiated one take exactly
  the same code path. Workers never import `apps/api/jobapply_api/routers`.
* `packages/browser` may import `packages/shared` only — it receives resolved answers
  and file paths, never a database session.
* `packages/ai` never performs I/O other than the provider HTTP call.
* Cross-package contracts are Pydantic models, so the same object crosses the API,
  the queue and the worker unchanged.
