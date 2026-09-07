# 9. Security Model

## Identity & sessions
* Argon2id password hashing (`argon2-cffi`), per-password salt, tuned parameters.
* Access JWT (15 min) + rotating refresh JWT (30 d) with a server-side `jti` denylist in
  Redis; logout and password change revoke all refresh tokens.
* Cookies: `HttpOnly`, `Secure`, `SameSite=Lax`, `__Host-` prefix in production.
* CSRF: double-submit token, required on every unsafe method for cookie-authenticated
  requests.
* Google OAuth via Authlib with PKCE + `state`; e-mail is trusted only when the
  provider marks it verified.

## Authorization
* Roles: `user`, `admin`. RBAC is enforced by FastAPI dependencies, and every
  repository method takes `user_id` — there is no unscoped query path for user data.
* Admin endpoints expose aggregates and failure diagnostics only. Password hashes,
  tokens, credential secrets and browser state are never returned to admins.

## Data protection
* TLS everywhere; HSTS in production.
* Envelope encryption (AES-256-GCM with a KMS/`SECRET_KEY`-derived data key) for
  credential vault entries and browser session blobs. Ciphertext columns are
  `deferred` in the ORM.
* The credential vault (`services/credential_service.py`) binds the owning user into
  the AEAD's associated data, so ciphertext moved into another user's row will not
  decrypt. `POST`, `PATCH` and `DELETE` exist; there is deliberately **no** endpoint
  that returns a secret. `CredentialVault.reveal()` is called from exactly one place —
  the automation worker, at the moment it signs in — and every call is audited with
  the credential's kind and host but never its value or its username.
* PostgreSQL at-rest encryption (RDS) and S3 SSE for objects; resume objects are
  private with short-lived presigned URLs.
* OTP codes are never persisted; they live in the worker's memory for the duration of
  one step.

## Input & output
* Pydantic validation on every request; strict types, length caps, enum-only status
  transitions.
* SQLAlchemy parameterized queries only; no string-built SQL.
* Uploads: extension + magic-byte + size checks (10 MB), stored under a random key,
  never served from the app origin.
* Frontend renders text only; no `dangerouslySetInnerHTML` for model or employer
  content. Strict CSP, `X-Content-Type-Options`, `Referrer-Policy`, frame denial.

## Logging & audit
* Structured JSON logs with a redaction filter for `password`, `token`, `cookie`,
  `authorization`, `otp`, `secret`, `api_key`.
* `audit_logs` records auth events, profile and preference changes, automation
  enable/disable, submissions, admin actions and deletions.

## Abuse & rate limiting
* Redis token buckets per IP (auth endpoints) and per user (applications/day and /hour).
* Application caps exist to protect the *user's* reputation and to prevent runaway
  automation — not to work around an employer's limits.

## Non-goals (explicit)
The platform does not solve CAPTCHAs, bypass MFA/OTP, evade bot detection, scrape
sources that forbid it, or access any account the user has not authorized.
