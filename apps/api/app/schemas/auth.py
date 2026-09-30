"""Auth request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserOut


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str | None = Field(default=None, max_length=200)
    timezone: str = Field(default="UTC", max_length=64)
    phone_e164: str | None = Field(default=None, max_length=20)

    @field_validator("phone_e164")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().replace(" ", "").replace("-", "")
        if not cleaned.startswith("+") or not cleaned[1:].isdigit():
            raise ValueError("phone must be in E.164 format, e.g. +2348012345678")
        return cleaned


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=200)


class SessionOut(BaseModel):
    id: str
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
