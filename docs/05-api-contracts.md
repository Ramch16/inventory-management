# 5. API Contracts

Base path `/api/v1`. JSON in / JSON out. Errors use a problem-details envelope:

```json
{ "error": { "code": "profile_incomplete", "message": "...", "details": {"missing": ["work_authorization"]} } }
```

Auth: access token in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie (`ja_access`),
refresh token in `ja_refresh` scoped to `/api/v1/auth`. A double-submit CSRF token is
required on all unsafe methods. Bearer tokens are accepted for programmatic clients.

## Phase 1 (implemented)

| Method | Path | Body → Response |
| --- | --- | --- |
| POST | `/auth/register` | `RegisterRequest` → `UserResponse` (+ cookies) |
| POST | `/auth/login` | `LoginRequest` → `UserResponse` (+ cookies) |
| POST | `/auth/logout` | – → `204` |
| POST | `/auth/refresh` | – → `UserResponse` (+ rotated cookies) |
| GET | `/auth/me` | – → `UserResponse` |
| POST | `/auth/verify-email/request` | – → `202` |
| POST | `/auth/verify-email/confirm` | `{token}` → `UserResponse` |
| POST | `/auth/password/forgot` | `{email}` → `202` (always) |
| POST | `/auth/password/reset` | `{token,password}` → `204` |
| POST | `/auth/password/change` | `{current,new}` → `204` |
| GET | `/auth/oauth/google/authorize` | – → `{authorize_url,state}` |
| GET | `/auth/oauth/google/callback` | `?code&state` → redirect + cookies |
| DELETE | `/auth/account` | `{password?}` → `204` (soft delete + purge job) |
| GET/PUT | `/profile` | `ProfileResponse` / `ProfileUpdate` |
| GET/PUT | `/profile/work-authorization` | explicit, never inferred |
| GET/POST | `/profile/education` · PUT/DELETE `/profile/education/{id}` | |
| GET/POST | `/profile/experience` · PUT/DELETE `/profile/experience/{id}` | |
| GET/POST | `/profile/skills` · PUT/DELETE `/profile/skills/{id}` | |
| GET/POST | `/profile/certifications` · PUT/DELETE `/profile/certifications/{id}` | |
| GET | `/profile/completeness` | `{score, missing, blocks_automation}` |
| POST | `/resumes/upload` | multipart `file` → `ResumeResponse` (parsed) |
| POST | `/resumes/text` | `{title, content}` → `ResumeResponse` |
| GET | `/resumes` · GET/PUT/DELETE `/resumes/{id}` | |
| POST | `/resumes/{id}/master` | promote to master |
| GET | `/resumes/{id}/download` | `302` to presigned URL |
| GET | `/analytics/summary` | dashboard counters |
| GET | `/notifications` · POST `/notifications/{id}/read` | |
| GET | `/health` · `/health/ready` | liveness / dependency readiness |

## Phase 2 (implemented)

```
POST /jobs/search                 { keywords, titles, locations, remote_only, sources[] }
                                  -> { fetched, created, duplicates, scored, errors[] }
GET  /jobs                        ?page&page_size&min_score&recommendation&company
                                  -> Page<JobCard>   (ordered by match score)
GET  /jobs/{id}                   -> JobDetail (posting + match analysis)
POST /jobs/{id}/match             -> MatchSummary   (rescore this job)
POST /jobs/rescore                -> { rescored }   (after a profile change)
POST /jobs/{id}/decision          { decision: approve|skip } -> MatchSummary
                                  # approve is refused when a hard requirement fails
GET  /preferences  PUT /preferences
GET  /job-sources                 -> configured sources and their enabled state
```

## Phase 3+ (contract fixed now, implemented per roadmap)

```
GET  /automation-settings  PUT /automation-settings
POST /automation/pause  POST /automation/resume        # global PAUSE ALL
POST /applications                { job_id, auto_submit } -> Application
GET  /applications                ?status&page -> Page<Application>
GET  /applications/{id}           -> ApplicationDetail (steps, questions, logs, shots)
POST /applications/{id}/start     -> 202
POST /applications/{id}/resume    -> 202
POST /applications/{id}/cancel    -> 204
PUT  /applications/{id}/status    { status, note }      # manual tracker updates
GET  /applications/export         -> text/csv
GET  /interventions               ?status -> Page<Intervention>
GET  /interventions/{id}          -> Intervention + screenshot URL
POST /interventions/{id}/continue { otp_code?, answers? } -> 202
POST /interventions/{id}/cancel   -> 204
GET  /analytics                   ?range -> series + breakdowns
GET  /admin/{users,jobs,applications,automation,errors,usage}    # role=admin
```

## Conventions

* Pagination: `?page=1&page_size=25` → `{items, page, page_size, total}`.
* Idempotency: `Idempotency-Key` honoured on `POST /applications` and
  `POST /applications/{id}/start`.
* All list endpoints are user-scoped in the repository layer, never by filter in the
  router.
* Long operations return `202 Accepted` with `{task_id}`; progress is read from the
  resource itself.
