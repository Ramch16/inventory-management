"""Password hashing, tokens and envelope encryption."""

from __future__ import annotations

import pytest
from jobapply_shared.errors import AuthenticationError
from jobapply_shared.logging import redact
from jobapply_shared.security import (
    decode_jwt,
    decrypt_blob,
    encrypt_blob,
    generate_url_token,
    hash_password,
    hash_token,
    issue_jwt,
    password_problems,
    verify_password,
)

SECRET = "test-secret-key-that-is-long-enough-for-tests"


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("Str0ngPassword!")
    second = hash_password("Str0ngPassword!")
    assert first != second, "each hash must use a fresh salt"
    assert "Str0ngPassword!" not in first
    assert verify_password("Str0ngPassword!", first)
    assert not verify_password("wrong", first)
    assert not verify_password("anything", None)


@pytest.mark.parametrize(
    ("password", "expected_problems"),
    [
        ("short1A", 1),
        ("alllowercase1", 1),
        ("NoDigitsHere!", 1),
        ("Str0ngPassword!", 0),
    ],
)
def test_password_policy(password, expected_problems):
    assert len(password_problems(password)) == expected_problems


def test_jwt_round_trip_and_type_enforcement():
    issued = issue_jwt(
        secret_key=SECRET,
        subject="user-1",
        token_type="access",
        ttl_seconds=60,
        extra_claims={"role": "user"},
    )
    payload = decode_jwt(issued.token, secret_key=SECRET, expected_type="access")
    assert payload["sub"] == "user-1"
    assert payload["role"] == "user"

    with pytest.raises(AuthenticationError):
        decode_jwt(issued.token, secret_key=SECRET, expected_type="refresh")
    with pytest.raises(AuthenticationError):
        decode_jwt(issued.token, secret_key="a-different-secret", expected_type="access")


def test_expired_jwt_is_rejected():
    issued = issue_jwt(secret_key=SECRET, subject="user-1", token_type="access", ttl_seconds=-10)
    with pytest.raises(AuthenticationError) as excinfo:
        decode_jwt(issued.token, secret_key=SECRET, expected_type="access")
    assert excinfo.value.code == "token_expired"


def test_single_use_tokens_are_stored_only_as_digests():
    token = generate_url_token()
    digest = hash_token(token)
    assert digest != token
    assert len(digest) == 64
    assert hash_token(token) == digest


def test_envelope_encryption_round_trip_and_context_binding():
    ciphertext = encrypt_blob(b"employer-password", secret_key=SECRET, context="vault")
    assert b"employer-password" not in ciphertext.encode()
    assert decrypt_blob(ciphertext, secret_key=SECRET, context="vault") == b"employer-password"

    with pytest.raises(Exception):
        decrypt_blob(ciphertext, secret_key=SECRET, context="browser-session")
    with pytest.raises(Exception):
        decrypt_blob(ciphertext, secret_key="another-secret-key-long-enough!!", context="vault")


def test_encryption_is_non_deterministic():
    a = encrypt_blob(b"secret", secret_key=SECRET)
    b = encrypt_blob(b"secret", secret_key=SECRET)
    assert a != b, "a fresh nonce must be used for every encryption"


def test_redaction_strips_sensitive_keys_and_bearer_tokens():
    payload = {
        "email": "a@example.com",
        "password": "hunter2",
        "otp_code": "123456",
        "nested": {"authorization": "Bearer abc.def.ghi"},
        "note": "Authorization: Bearer abc.def.ghi",
    }
    cleaned = redact(payload)
    assert cleaned["password"] == "[redacted]"
    assert cleaned["otp_code"] == "[redacted]"
    assert cleaned["nested"]["authorization"] == "[redacted]"
    assert "abc.def.ghi" not in cleaned["note"]
    assert cleaned["email"] == "a@example.com"
