"""Password hashing, token issuance and envelope encryption.

No plaintext password is ever stored or logged. Single-use tokens (e-mail
verification, password reset) are stored only as SHA-256 digests, so a database read
does not yield a usable token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from jobapply_shared.errors import AuthenticationError

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)

TokenType = Literal["access", "refresh"]
MIN_PASSWORD_LENGTH = 10


# --------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def password_problems(password: str) -> list[str]:
    """Return a list of policy violations; empty means acceptable."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if password.lower() == password or password.upper() == password:
        problems.append("must mix upper and lower case letters")
    if not any(char.isdigit() for char in password):
        problems.append("must contain a digit")
    return problems


# ------------------------------------------------------------------------------ tokens
@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: str
    expires_at: datetime


def issue_jwt(
    *,
    secret_key: str,
    subject: str,
    token_type: TokenType,
    ttl_seconds: int,
    extra_claims: dict[str, Any] | None = None,
) -> IssuedToken:
    now = datetime.now(tz=UTC)
    expires_at = now + timedelta(seconds=ttl_seconds)
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return IssuedToken(jwt.encode(payload, secret_key, algorithm="HS256"), jti, expires_at)


def decode_jwt(
    token: str, *, secret_key: str, expected_type: TokenType | None = None
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token", code="token_invalid") from exc
    if expected_type and payload.get("typ") != expected_type:
        raise AuthenticationError("Invalid token type", code="token_invalid")
    return payload


def generate_url_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


# -------------------------------------------------------------------------- encryption
def _derive_key(secret_key: str, context: str) -> bytes:
    return hashlib.blake2b(
        secret_key.encode("utf-8"),
        salt=b"jobapply-kdf",
        person=context.encode("utf-8")[:16],
        digest_size=32,
    ).digest()


def encrypt_blob(plaintext: bytes, *, secret_key: str, context: str = "vault") -> str:
    """AES-256-GCM envelope encryption. Returns ``v1.<nonce>.<ciphertext>`` base64url."""
    key = _derive_key(secret_key, context)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, context.encode("utf-8"))
    encode = lambda raw: base64.urlsafe_b64encode(raw).decode("ascii")  # noqa: E731
    return f"v1.{encode(nonce)}.{encode(ciphertext)}"


def decrypt_blob(payload: str, *, secret_key: str, context: str = "vault") -> bytes:
    version, nonce_b64, ciphertext_b64 = payload.split(".", 2)
    if version != "v1":
        raise ValueError(f"Unsupported ciphertext version: {version}")
    key = _derive_key(secret_key, context)
    nonce = base64.urlsafe_b64decode(nonce_b64)
    ciphertext = base64.urlsafe_b64decode(ciphertext_b64)
    return AESGCM(key).decrypt(nonce, ciphertext, context.encode("utf-8"))
