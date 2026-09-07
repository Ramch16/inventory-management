"""Credential vault endpoints.

There is no endpoint that returns a secret. Values go in and are never handed back —
not to the browser, not to an admin, not to this API. Only an automation worker
decrypts one, at the moment it signs in on the user's behalf.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, status
from jobapply_db.models import Credential
from jobapply_shared.enums import CredentialKind
from pydantic import BaseModel, Field

from jobapply_api.deps import CurrentUser, SessionDep, SettingsDep
from jobapply_api.services.credential_service import CredentialVault

router = APIRouter(prefix="/credentials", tags=["credentials"])


class CredentialCreate(BaseModel):
    label: str = Field(min_length=1, max_length=180)
    kind: CredentialKind
    host: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    #: Write-only. Never echoed by any response model in this module.
    secret: str | None = Field(default=None, max_length=1024)


class CredentialUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=180)
    host: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    secret: str | None = Field(default=None, max_length=1024)


class CredentialOut(BaseModel):
    """Everything a user may see about a stored credential — which is not the secret."""

    id: uuid.UUID
    label: str
    kind: str
    host: str | None
    username: str | None
    has_secret: bool
    last_used_at: datetime | None
    created_at: datetime


def _out(credential: Credential) -> CredentialOut:
    return CredentialOut(
        id=credential.id,
        label=credential.label,
        kind=credential.kind,
        host=credential.host,
        username=credential.username,
        has_secret=bool(credential.secret_encrypted),
        last_used_at=credential.last_used_at,
        created_at=credential.created_at,
    )


def _vault(db: SessionDep, settings: SettingsDep) -> CredentialVault:
    return CredentialVault(db, secret_key=settings.secret_key)


@router.get("", response_model=list[CredentialOut])
def list_credentials(
    user: CurrentUser, db: SessionDep, settings: SettingsDep
) -> list[CredentialOut]:
    return [_out(credential) for credential in _vault(db, settings).list_for(user.id)]


@router.post("", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
def create_credential(
    payload: CredentialCreate,
    user: CurrentUser,
    db: SessionDep,
    settings: SettingsDep,
) -> CredentialOut:
    vault = _vault(db, settings)
    credential = vault.create(
        user.id,
        label=payload.label,
        kind=payload.kind,
        host=payload.host,
        username=payload.username,
        secret=payload.secret,
    )
    db.commit()
    db.refresh(credential)
    return _out(credential)


@router.patch("/{credential_id}", response_model=CredentialOut)
def update_credential(
    credential_id: uuid.UUID,
    payload: CredentialUpdate,
    user: CurrentUser,
    db: SessionDep,
    settings: SettingsDep,
) -> CredentialOut:
    credential = _vault(db, settings).update(
        user.id,
        credential_id,
        label=payload.label,
        host=payload.host,
        username=payload.username,
        secret=payload.secret,
    )
    db.commit()
    db.refresh(credential)
    return _out(credential)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    credential_id: uuid.UUID, user: CurrentUser, db: SessionDep, settings: SettingsDep
) -> None:
    _vault(db, settings).delete(user.id, credential_id)
    db.commit()
