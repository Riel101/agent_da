"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router, internal_router, system_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("DEBUG" if settings.debug else "INFO")
    logger.info(
        "starting %s (%s) llm=%s scheduler=%s",
        settings.app_name,
        settings.environment,
        settings.llm_model,
        settings.scheduler_enabled,
    )

    # Local development convenience: create tables when there are no migrations
    # to run (SQLite only — production always goes through Alembic).
    if settings.is_sqlite:
        from app.db.base import Base
        from app.db.session import get_engine

        import app.models  # noqa: F401 - registers the mappers

        engine = get_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    from app.agents.checkpointer import get_checkpointer

    await get_checkpointer()

    from app.scheduler.scheduler import shutdown_scheduler, start_scheduler

    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
        from app.agents.runner import runner
        from app.agents.checkpointer import close_checkpointer
        from app.db.session import dispose_engine
        from app.services.plan_service import wait_for_background

        await wait_for_background(timeout=20)
        runner.reset()
        await close_checkpointer()
        await dispose_engine()
        logger.info("shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent DA",
        version="0.1.0",
        description=(
            "An agent that breaks a long-term agenda into daily sub-agendas, "
            "turns each day into to-dos, and reminds you until it is done."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(system_router)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(internal_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": "/healthz",
        }

    return app


app = create_app()
