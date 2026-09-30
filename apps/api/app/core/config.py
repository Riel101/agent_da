"""Application configuration.

All tunables live here so behaviour can be changed without a migration.
Values are read from the environment (and an optional ``.env`` file).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "apps/api/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    app_name: str = "agent_da"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_prefix: str = "/api/v1"
    public_base_url: str = "http://localhost:8000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # ------------------------------------------------------------- database
    # Postgres in production (Render), SQLite for local development and tests.
    database_url: str = "sqlite+aiosqlite:///./agent_da.db"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ----------------------------------------------------------------- auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 30
    # Verification is optional per product decision.
    email_verification_required: bool = False
    signup_rate_limit_per_minute: int = 10
    generate_rate_limit_per_hour: int = 5

    # ------------------------------------------------------------------ llm
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    llm_temperature: float = 0.4
    llm_max_tokens: int = 8192
    llm_timeout_seconds: int = 180
    llm_max_retries: int = 3
    # Chunk the plan into windows this size when the timeframe is longer.
    plan_chunk_days: int = 7
    plan_chunk_threshold_days: int = 21
    max_repair_passes: int = 2
    # LangGraph checkpointer: "memory" for local/test, "postgres" in production.
    checkpointer_backend: Literal["memory", "postgres"] = "memory"
    #: When false, /generate creates the draft but does not run the graph in the
    #: background. Useful for tests and for running generation in a separate worker.
    agent_autostart: bool = True

    # -------------------------------------------------------------- reminders
    scheduler_enabled: bool = True
    dispatch_interval_seconds: int = 60
    materialize_interval_minutes: int = 30
    day_close_interval_minutes: int = 30
    dispatch_batch_size: int = 50
    dispatch_max_attempts: int = 3
    # Pre-expand this many days of to-dos at approval time.
    preexpand_days: int = 3
    reminder_retention_days: int = 90
    motivation_enabled: bool = True

    # ----------------------------------------------------------------- email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Agent DA <no-reply@agentda.local>"
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 20

    # -------------------------------------------------------------- whatsapp
    # auto -> use twilio if configured, else meta, else console.
    whatsapp_provider: Literal["auto", "twilio", "meta", "console"] = "auto"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    # Optional pre-approved template SID (required outside the 24h window).
    twilio_content_sid: str = ""
    meta_whatsapp_token: str = ""
    meta_whatsapp_phone_number_id: str = ""
    meta_whatsapp_api_version: str = "v21.0"
    # Fall back to email when WhatsApp cannot be delivered.
    fallback_to_email: bool = True

    # -------------------------------------------------------------- internal
    internal_token: str = "dev-internal-token"

    # ---------------------------------------------------------------- points
    task_completed_points: int = 10
    day_complete_bonus: int = 25
    streak_milestone_every: int = 7
    streak_milestone_bonus: int = 100
    agenda_complete_bonus: int = 250
    perfect_run_bonus: int = 500
    # Product decision: missed days cost points.
    missed_day_deduction: int = 5
    allow_point_deductions: bool = True

    # -------------------------------------------------------------- behavior
    max_timeframe_days: int = 90
    min_timeframe_days: int = 1
    # Product decision: overdue tasks are left marked missed, not carried forward.
    rollover_overdue_tasks: bool = False
    overdue_grace_days: int = 0
    # 0 == unlimited active agendas per user.
    max_active_agendas_per_user: int = 0
    cancel_unapproved_drafts_after_days: int = 30
    min_description_chars: int = 20
    todos_per_day_min: int = 3
    todos_per_day_max: int = 6

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Normalise the DSN for the async driver.

        Render (and Heroku-style providers) hand out ``postgres://`` URLs which
        SQLAlchemy cannot use directly.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Synchronous DSN, used by Alembic."""
        url = self.sqlalchemy_database_url
        return url.replace("+asyncpg", "+psycopg").replace("+aiosqlite", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
