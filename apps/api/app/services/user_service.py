"""Account creation, login and token rotation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AuthenticationError, ConflictError, NotFoundError
from app.core.security import (
    create_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == normalize_email(email)))


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return user


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    timezone: str = "UTC",
    phone_e164: str | None = None,
) -> User:
    normalized = normalize_email(email)
    if await get_by_email(session, normalized):
        raise ConflictError("An account with that email already exists", code="EMAIL_TAKEN")

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        full_name=full_name,
        timezone=timezone or "UTC",
        phone_e164=phone_e164,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = await get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Email or password is incorrect", code="BAD_CREDENTIALS")
    if not user.is_active:
        raise AuthenticationError("This account is disabled", code="ACCOUNT_DISABLED")

    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user


async def update_user(
    session: AsyncSession,
    user: User,
    *,
    full_name: str | None = None,
    timezone: str | None = None,
    phone_e164: str | None = None,
) -> User:
    if full_name is not None:
        user.full_name = full_name
    if timezone is not None:
        user.timezone = timezone
    if phone_e164 is not None:
        user.phone_e164 = phone_e164
    await session.flush()
    return user


async def issue_tokens(
    session: AsyncSession,
    user: User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, object]:
    refresh = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
            user_agent=(user_agent or "")[:300] or None,
            ip_address=(ip_address or "")[:64] or None,
        )
    )
    await session.flush()

    return {
        "user": user,
        "access_token": create_token(str(user.id), "access"),
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_ttl_minutes * 60,
    }


async def rotate_refresh_token(
    session: AsyncSession,
    token: str,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, object]:
    digest = hash_token(token)
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == digest).with_for_update()
    )
    if row is None:
        raise AuthenticationError("Refresh token is not recognised", code="TOKEN_INVALID")
    if row.revoked_at is not None:
        # Re-use of a rotated token: assume compromise and drop every session.
        # Commit the revocation first — raising would otherwise roll it back.
        await revoke_all(session, row.user_id)
        await session.commit()
        raise AuthenticationError("Refresh token has already been used", code="TOKEN_REUSED")
    if row.expires_at is None or _as_utc(row.expires_at) < datetime.now(UTC):
        raise AuthenticationError("Refresh token has expired", code="TOKEN_EXPIRED")

    row.revoked_at = datetime.now(UTC)
    user = await get_user(session, row.user_id)
    return await issue_tokens(session, user, user_agent=user_agent, ip_address=ip_address)


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    digest = hash_token(token)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == digest, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def list_sessions(session: AsyncSession, user_id: uuid.UUID) -> list[RefreshToken]:
    rows = await session.execute(
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .order_by(RefreshToken.created_at.desc())
        .limit(50)
    )
    return list(rows.scalars().all())


def _as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat those as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
