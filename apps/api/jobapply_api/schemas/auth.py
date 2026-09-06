"""Authentication request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from jobapply_shared.security import password_problems
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from jobapply_api.schemas.common import ORMModel


def _validate_password(value: str) -> str:
    problems = password_problems(value)
    if problems:
        raise ValueError("Password " + "; ".join(problems))
    return value


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserResponse(ORMModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    is_active: bool
    email_verified_at: datetime | None = None
    automation_paused: bool
    onboarding_completed_at: datetime | None = None
    created_at: datetime


class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class TokenConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=10, max_length=500)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=10, max_length=500)
    password: str = Field(min_length=10, max_length=200)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class AccountDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str | None = Field(default=None, max_length=200)
    confirmation: str = Field(description="Must be the literal string DELETE")

    @field_validator("confirmation")
    @classmethod
    def check_confirmation(cls, value: str) -> str:
        if value != "DELETE":
            raise ValueError("Type DELETE to confirm account deletion")
        return value


class OAuthAuthorizeResponse(BaseModel):
    authorize_url: str
    state: str
