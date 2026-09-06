# 6. Background Worker Architecture

Celery over Redis. Four logical queues so a slow browser run cannot starve matching:

| Queue | Concurrency | Tasks |
| --- | --- | --- |
| `discovery` | 4 (prefork) | `jobs.discover`, `jobs.normalize`, `jobs.expire` |
| `matching` | 8 (prefork) | `match.score_user_jobs`, `match.rescore_on_profile_change` |
| `resumes` | 4 (prefork) | `resume.parse`, `resume.tailor`, `resume.render`, `resume.score` |
| `automation` | 2 per worker pod (solo/threads) | `apply.run`, `apply.resume_after_verification`, `apply.cleanup_sessions` |
| `notifications` | 4 | `email.send`, `notify.dispatch` |

## Rules

1. Task payloads contain identifiers only. Workers reload state inside a transaction.
2. Every task is idempotent: it checks the row's current status and no-ops if the
   transition has already happened.
3. `apply.run` takes a Redis lock `lock:apply:{user_id}` so a user never has two
   browser runs at once, plus per-user token buckets for the hourly/daily caps.
4. Retries: `autoretry_for=(TransientError,)`, `retry_backoff=True`,
   `retry_backoff_max=600`, `retry_jitter=True`, `max_retries=5`. Permanent failure
   classes (`UNSUPPORTED_FORM`, `AUTHENTICATION_REQUIRED`, `CAPTCHA`, `OTP`,
   `MISSING_DATA`) are never retried automatically.
5. Beat schedule: discovery every 30 min per enabled source, match sweep every 15 min,
   session reaper every 5 min, expired-job sweep hourly, digest e-mail daily.
6. Worker health is reported to `worker_heartbeats` in Redis; `/health/ready` fails if
   no automation worker has checked in within 90 s.
