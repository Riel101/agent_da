"""Authentication endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.errors import AuthenticationError, ValidationError
from app.core.logging import get_logger
from app.core.security import create_token, decode_token
from app.core.timezones import utc_now
from app.db.session import get_db
from app.integrations.channels.base import OutboundMessage
from app.integrations.channels.registry import email_sender
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SessionOut,
    SignupRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.schemas.common import MessageOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


def _client(request: Request) -> tuple[str | None, str | None]:
    agent = request.headers.get("user-agent")
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else None)
    return agent, ip


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest, request: Request, session: AsyncSession = Depends(get_db)
) -> AuthResponse:
    ratelimit.enforce(
        ratelimit.client_key(request, "signup"),
        limit=settings.signup_rate_limit_per_minute,
        window_seconds=60,
    )
    user = await user_service.create_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        timezone=payload.timezone,
        phone_e164=payload.phone_e164,
    )
    agent, ip = _client(request)
    result = await user_service.issue_tokens(session, user, user_agent=agent, ip_address=ip)
    await session.commit()
    return AuthResponse.model_validate(result)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_db)
) -> AuthResponse:
    ratelimit.enforce(
        ratelimit.client_key(request, "login"),
        limit=settings.signup_rate_limit_per_minute,
        window_seconds=60,
    )
    user = await user_service.authenticate(session, email=payload.email, password=payload.password)
    agent, ip = _client(request)
    result = await user_service.issue_tokens(session, user, user_agent=agent, ip_address=ip)
    await session.commit()
    return AuthResponse.model_validate(result)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, request: Request, session: AsyncSession = Depends(get_db)
) -> TokenPair:
    ratelimit.enforce(
        ratelimit.client_key(request, "refresh"), limit=60, window_seconds=60
    )
    agent, ip = _client(request)
    result = await user_service.rotate_refresh_token(
        session, payload.refresh_token, user_agent=agent, ip_address=ip
    )
    await session.commit()
    return TokenPair.model_validate(result)


@router.post("/logout", response_model=MessageOut)
async def logout(
    payload: RefreshRequest, session: AsyncSession = Depends(get_db)
) -> MessageOut:
    await user_service.revoke_refresh_token(session, payload.refresh_token)
    await session.commit()
    return MessageOut(detail="Signed out")


@router.post("/logout-all", response_model=MessageOut)
async def logout_all(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> MessageOut:
    await user_service.revoke_all(session, user.id)
    await session.commit()
    return MessageOut(detail="All sessions revoked")


@router.get("/sessions", response_model=list[SessionOut])
async def sessions(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> list[SessionOut]:
    rows = await user_service.list_sessions(session, user.id)
    return [
        SessionOut(
            id=str(row.id),
            user_agent=row.user_agent,
            ip_address=row.ip_address,
            created_at=row.created_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]


@router.post("/verify-email", response_model=MessageOut)
async def verify_email(
    payload: VerifyEmailRequest, session: AsyncSession = Depends(get_db)
) -> MessageOut:
    data = decode_token(payload.token, "email_verify")
    user = await session.get(User, uuid.UUID(str(data["sub"])))
    if user is None:
        raise AuthenticationError("Account no longer exists", code="USER_NOT_FOUND")
    user.email_verified_at = user.email_verified_at or utc_now()
    await session.commit()
    return MessageOut(detail="Email verified")


@router.post("/verify-email/request", response_model=MessageOut)
async def request_verification(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> MessageOut:
    if user.email_verified_at is not None:
        return MessageOut(detail="Email is already verified")

    token = create_token(str(user.id), "email_verify")
    link = f"{settings.public_base_url}/verify-email?token={token}"
    await email_sender().send(
        OutboundMessage(
            to=user.email,
            subject="Verify your Agent DA email",
            body=f"Confirm your email address to receive reminders:\n\n{link}",
        )
    )
    return MessageOut(detail="Verification email sent")


@router.post("/forgot-password", response_model=MessageOut)
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, session: AsyncSession = Depends(get_db)
) -> MessageOut:
    ratelimit.enforce(
        ratelimit.client_key(request, "forgot"), limit=10, window_seconds=3600
    )
    user = await user_service.get_by_email(session, payload.email)
    if user is not None:
        token = create_token(str(user.id), "password_reset")
        link = f"{settings.public_base_url}/reset-password?token={token}"
        await email_sender().send(
            OutboundMessage(
                to=user.email,
                subject="Reset your Agent DA password",
                body=f"Use this link to choose a new password:\n\n{link}",
            )
        )
    # Always the same response so the endpoint cannot enumerate accounts.
    return MessageOut(detail="If that email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageOut)
async def reset_password(
    payload: ResetPasswordRequest, session: AsyncSession = Depends(get_db)
) -> MessageOut:
    data = decode_token(payload.token, "password_reset")
    user = await session.get(User, uuid.UUID(str(data["sub"])))
    if user is None:
        raise AuthenticationError("Account no longer exists", code="USER_NOT_FOUND")

    from app.core.security import hash_password

    if len(payload.new_password) < 8:
        raise ValidationError("Password must be at least 8 characters", code="WEAK_PASSWORD")
    user.password_hash = hash_password(payload.new_password)
    await user_service.revoke_all(session, user.id)
    await session.commit()
    return MessageOut(detail="Password updated. Please sign in again.")
