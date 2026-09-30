"""Request dependencies: authentication and internal-token guard."""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User


def _bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_db)
) -> User:
    token = _bearer(request)
    if token is None:
        raise AuthenticationError("Missing bearer token", code="NO_TOKEN")

    payload = decode_token(token, "access")
    subject = payload.get("sub")
    try:
        user_id = uuid.UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Malformed token subject", code="TOKEN_INVALID") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise AuthenticationError("Account no longer exists", code="USER_NOT_FOUND")
    if not user.is_active:
        raise AuthenticationError("This account is disabled", code="ACCOUNT_DISABLED")
    return user


async def require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    if not settings.internal_token:
        raise PermissionDeniedError("Internal endpoints are disabled")
    if x_internal_token != settings.internal_token:
        raise PermissionDeniedError("Invalid internal token", code="BAD_INTERNAL_TOKEN")
