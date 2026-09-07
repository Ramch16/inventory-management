"""The credential vault.

A credential exists so an automation worker can sign in to a job board *as the user*,
on a site the user has told us to use. The rules that make that acceptable are all in
this module:

* the secret is encrypted with AES-256-GCM before it reaches the database, under a key
  derived for one user, so ciphertext copied into another user's row will not decrypt;
* nothing here ever returns a secret to an HTTP response — ``reveal`` exists for the
  automation worker and is not wired to a route;
* the plaintext is never logged, never placed in an audit entry, and never held longer
  than the call that needs it;
* every read is recorded, so a user can see when their credential was used.

OAuth is preferable wherever a provider offers it. Stored passwords are the fallback
for sites that offer nothing else, and the user has to add them deliberately.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jobapply_db.models import Credential
from jobapply_shared.enums import CredentialKind
from jobapply_shared.errors import NotFoundError, ValidationError_
from jobapply_shared.logging import get_logger
from jobapply_shared.security import decrypt_blob, encrypt_blob
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobapply_api.services import audit

logger = get_logger(__name__)

#: Bound into the AEAD's associated data, so a ciphertext is only valid for the user
#: it was written for and only as a vault secret.
VAULT_CONTEXT = "vault:credential"

#: Kinds whose secret is a password. OAuth entries hold a refresh token instead, and
#: an SSO entry holds nothing at all — the user signs in during an intervention.
SECRET_REQUIRED_KINDS = frozenset({CredentialKind.PASSWORD, CredentialKind.API_TOKEN})


def _context(user_id: uuid.UUID) -> str:
    return f"{VAULT_CONTEXT}:{user_id}"


class CredentialVault:
    """Create, list, update and delete vault entries. Reads are for workers only."""

    def __init__(self, db: Session, *, secret_key: str) -> None:
        self.db = db
        self.secret_key = secret_key

    # ------------------------------------------------------------------ queries
    def list_for(self, user_id: uuid.UUID) -> list[Credential]:
        return list(
            self.db.execute(
                select(Credential)
                .where(Credential.user_id == user_id)
                .order_by(Credential.created_at.desc())
            )
            .scalars()
            .all()
        )

    def get(self, user_id: uuid.UUID, credential_id: uuid.UUID) -> Credential:
        credential = self.db.execute(
            select(Credential).where(Credential.id == credential_id, Credential.user_id == user_id)
        ).scalar_one_or_none()
        if credential is None:
            raise NotFoundError("Credential not found.", code="credential_not_found")
        return credential

    # ------------------------------------------------------------------ writes
    def create(
        self,
        user_id: uuid.UUID,
        *,
        label: str,
        kind: CredentialKind,
        host: str | None,
        username: str | None,
        secret: str | None,
    ) -> Credential:
        self._require_secret(kind, secret)
        credential = Credential(
            user_id=user_id,
            label=label.strip(),
            kind=str(kind),
            host=_normalize_host(host),
            username=(username or "").strip() or None,
            secret_encrypted=self._seal(user_id, secret),
        )
        self.db.add(credential)
        self.db.flush()
        audit.record(
            self.db,
            action="credential.created",
            actor_user_id=user_id,
            entity_type="credential",
            entity_id=credential.id,
            # Deliberately no secret, no username: what was stored, not what it is.
            data={"kind": str(kind), "host": credential.host},
        )
        return credential

    def update(
        self,
        user_id: uuid.UUID,
        credential_id: uuid.UUID,
        *,
        label: str | None = None,
        username: str | None = None,
        host: str | None = None,
        secret: str | None = None,
    ) -> Credential:
        credential = self.get(user_id, credential_id)
        if label is not None:
            credential.label = label.strip()
        if username is not None:
            credential.username = username.strip() or None
        if host is not None:
            credential.host = _normalize_host(host)
        if secret is not None:
            # An empty string is a request to clear the secret, which is only legal
            # for kinds that do not need one.
            self._require_secret(CredentialKind(credential.kind), secret or None)
            credential.secret_encrypted = self._seal(user_id, secret or None)
        self.db.flush()
        audit.record(
            self.db,
            action="credential.updated",
            actor_user_id=user_id,
            entity_type="credential",
            entity_id=credential.id,
            data={"secret_rotated": secret is not None},
        )
        return credential

    def delete(self, user_id: uuid.UUID, credential_id: uuid.UUID) -> None:
        credential = self.get(user_id, credential_id)
        self.db.delete(credential)
        audit.record(
            self.db,
            action="credential.deleted",
            actor_user_id=user_id,
            entity_type="credential",
            entity_id=credential_id,
            data={"kind": credential.kind},
        )

    # ------------------------------------------------------------------- reveal
    def reveal(self, user_id: uuid.UUID, credential_id: uuid.UUID) -> str | None:
        """Decrypt one secret for immediate use by an automation worker.

        Not reachable over HTTP. The caller must use the value and drop it; it is not
        returned to a browser, written to a log, or placed in a task payload.
        """
        credential = self.get(user_id, credential_id)
        if not credential.secret_encrypted:
            return None
        plaintext = decrypt_blob(
            credential.secret_encrypted, secret_key=self.secret_key, context=_context(user_id)
        )
        credential.last_used_at = datetime.now(tz=UTC)
        audit.record(
            self.db,
            action="credential.used",
            actor_user_id=user_id,
            entity_type="credential",
            entity_id=credential.id,
            data={"kind": credential.kind, "host": credential.host},
        )
        logger.info(
            "credential.revealed",
            extra={
                "context": {
                    "event": "credential.revealed",
                    "credential_id": str(credential.id),
                    "kind": credential.kind,
                }
            },
        )
        return plaintext.decode("utf-8")

    # ------------------------------------------------------------------ helpers
    def _seal(self, user_id: uuid.UUID, secret: str | None) -> str | None:
        if not secret:
            return None
        return encrypt_blob(
            secret.encode("utf-8"), secret_key=self.secret_key, context=_context(user_id)
        )

    @staticmethod
    def _require_secret(kind: CredentialKind, secret: str | None) -> None:
        if kind in SECRET_REQUIRED_KINDS and not secret:
            raise ValidationError_(f"A {kind} credential needs a secret.", code="secret_required")


def _normalize_host(host: str | None) -> str | None:
    """Store a bare hostname, so one entry matches a site however its URL was typed."""
    if not host:
        return None
    cleaned = host.strip().lower()
    cleaned = cleaned.split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0]
    return cleaned.removeprefix("www.") or None
