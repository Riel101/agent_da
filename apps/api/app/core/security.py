"""Password hashing and JWT helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings
from app.core.errors import AuthenticationError

TokenType = Literal["access", "refresh", "email_verify", "password_reset"]

_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a password with bcrypt.

    bcrypt silently truncates at 72 bytes; we pre-hash long passwords with
    SHA-256 so the full entropy is preserved.
    """
    raw = _prepare_password(password)
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare_password(password), password_hash.encode())
    except (ValueError, TypeError):
        return False


def _prepare_password(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raw = hashlib.sha256(raw).hexdigest().encode("ascii")
    return raw


def create_token(
    subject: str,
    token_type: TokenType = "access",
    *,
    expires_delta: timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = _default_ttl(token_type)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired", code="TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token", code="TOKEN_INVALID") from exc

    if expected_type and payload.get("type") != expected_type:
        raise AuthenticationError("Unexpected token type", code="TOKEN_WRONG_TYPE")
    return payload


def _default_ttl(token_type: TokenType) -> timedelta:
    if token_type == "access":
        return timedelta(minutes=settings.access_token_ttl_minutes)
    if token_type == "refresh":
        return timedelta(days=settings.refresh_token_ttl_days)
    return timedelta(hours=24)


def new_refresh_token() -> str:
    """Opaque refresh token; only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
