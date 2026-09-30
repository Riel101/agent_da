"""Authentication behaviour."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_is_public(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_signup_then_read_me(client, registered):
    response = await client.get("/api/v1/users/me", headers=registered["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["points_balance"] == 0
    assert body["current_streak"] == 0


@pytest.mark.asyncio
async def test_signup_normalises_email_and_rejects_duplicates(client, registered):
    duplicate = await client.post(
        "/api/v1/auth/signup",
        json={"email": "ADA@Example.com", "password": "another-good-password"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_TAKEN"


@pytest.mark.asyncio
async def test_login_and_bad_password(client, registered):
    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "correct-horse-battery"},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "BAD_CREDENTIALS"


@pytest.mark.asyncio
async def test_refresh_rotates_and_detects_reuse(client, registered):
    first = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]}
    )
    assert first.status_code == 200
    rotated = first.json()["refresh_token"]
    assert rotated != registered["refresh_token"]

    reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]}
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "TOKEN_REUSED"

    # Every session is invalidated when token reuse is detected.
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated})
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_a_token(client):
    response = await client.get("/api/v1/agendas")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NO_TOKEN"


@pytest.mark.asyncio
async def test_password_reset_flow(client, registered):
    request = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "ada@example.com"}
    )
    assert request.status_code == 200

    from app.core.security import create_token

    user_id = registered["user"]["id"]
    token = create_token(user_id, "password_reset")
    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "brand-new-password"},
    )
    assert reset.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "brand-new-password"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_weak_password_rejected(client):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_whatsapp_requires_a_phone_number(client, registered):
    response = await client.post(
        "/api/v1/agendas",
        headers=registered["headers"],
        json={
            "title": "Run a half marathon",
            "description": "Train consistently and finish a half marathon in under two hours.",
            "timeframe_days": 10,
            "reminder_channel": "whatsapp",
            "reminder_time": "07:00",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PHONE_REQUIRED"
