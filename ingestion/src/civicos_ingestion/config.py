from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(validation_alias="DATABASE_URL")
    s3_endpoint_url: str | None = Field(default=None, validation_alias="S3_ENDPOINT_URL")
    s3_bucket: str = Field(default="civicos-raw", validation_alias="S3_BUCKET")
    s3_access_key: str = Field(validation_alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(validation_alias="S3_SECRET_KEY")
    discovery_poll_seconds: float = Field(default=5, validation_alias="CIVICOS_DISCOVERY_POLL_SECONDS")
    discovery_user_agent: str = Field(
        default="CivicOS-Discovery/0.1 (+https://github.com/civicos/civicos)",
        validation_alias="CIVICOS_DISCOVERY_USER_AGENT",
    )
    qdrant_url: str | None = Field(default=None, validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="civicos_documents", validation_alias="QDRANT_COLLECTION")
    embedding_base_url: str | None = Field(default=None, validation_alias="EMBEDDING_BASE_URL")
    embedding_model: str | None = Field(default=None, validation_alias="EMBEDDING_MODEL")
    embedding_api_key: str | None = Field(default=None, validation_alias="EMBEDDING_API_KEY")
    embedding_max_characters: int = Field(default=30000, validation_alias="CIVICOS_EMBEDDING_MAX_CHARACTERS")
    briefing_timezone: str = Field(default="UTC", validation_alias="CIVICOS_BRIEFING_TIMEZONE")
    briefing_near_term_days: int = Field(default=7, ge=1, le=30, validation_alias="CIVICOS_BRIEFING_NEAR_TERM_DAYS")
    briefing_lookahead_days: int = Field(default=14, ge=2, le=90, validation_alias="CIVICOS_BRIEFING_LOOKAHEAD_DAYS")
    briefing_section_limit: int = Field(default=10, ge=1, le=50, validation_alias="CIVICOS_BRIEFING_SECTION_LIMIT")
    founder_brief_minimum_score: int = Field(
        default=70, ge=0, le=100, validation_alias="CIVICOS_FOUNDER_BRIEF_MINIMUM_SCORE"
    )
    founder_brief_section_limit: int = Field(
        default=8, ge=1, le=50, validation_alias="CIVICOS_FOUNDER_BRIEF_SECTION_LIMIT"
    )
    canonical_backfill_on_start: bool = Field(
        default=False, validation_alias="CIVICOS_CANONICAL_BACKFILL_ON_START"
    )

    @field_validator(
        "s3_endpoint_url",
        "qdrant_url",
        "qdrant_api_key",
        "embedding_base_url",
        "embedding_model",
        "embedding_api_key",
        mode="before",
    )
    @classmethod
    def empty_endpoint_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("briefing_timezone")
    @classmethod
    def valid_briefing_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("CIVICOS_BRIEFING_TIMEZONE must be an IANA timezone") from error
        return value
