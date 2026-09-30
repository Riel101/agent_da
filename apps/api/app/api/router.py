"""API routers."""

from fastapi import APIRouter

from app.api.routers import agendas, auth, dashboard, health, internal, todos, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(agendas.router)
api_router.include_router(todos.router)
api_router.include_router(dashboard.router)

system_router = APIRouter()
system_router.include_router(health.router)

internal_router = APIRouter()
internal_router.include_router(internal.router)

__all__ = ["api_router", "internal_router", "system_router"]
