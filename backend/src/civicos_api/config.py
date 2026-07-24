from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded exclusively from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", validation_alias="CIVICOS_ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="CIVICOS_LOG_LEVEL")
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:3000")],
        validation_alias="CIVICOS_API_CORS_ORIGINS",
    )
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"],
        validation_alias="CIVICOS_ALLOWED_HOSTS",
    )
    auth_mode: Literal["development", "oidc", "founder_secret"] = Field(
        default="development", validation_alias="CIVICOS_AUTH_MODE"
    )
    auth_issuer: AnyHttpUrl | None = Field(default=None, validation_alias="CIVICOS_AUTH_ISSUER")
    auth_audience: str | None = Field(default=None, validation_alias="CIVICOS_AUTH_AUDIENCE")
    auth_jwks_url: AnyHttpUrl | None = Field(default=None, validation_alias="CIVICOS_AUTH_JWKS_URL")
    auth_organization_claim: str = Field(
        default="organization_id", min_length=1, validation_alias="CIVICOS_AUTH_ORGANIZATION_CLAIM"
    )
    founder_auth_secret: SecretStr | None = Field(
        default=None, validation_alias="CIVICOS_FOUNDER_AUTH_SECRET"
    )
    founder_external_subject: str = Field(
        default="civicos-founder", min_length=1, validation_alias="CIVICOS_FOUNDER_EXTERNAL_SUBJECT"
    )
    founder_email: str = Field(
        default="founder@civicos.local", min_length=3, validation_alias="CIVICOS_FOUNDER_EMAIL"
    )
    founder_display_name: str = Field(
        default="CivicOS Founder", min_length=1, validation_alias="CIVICOS_FOUNDER_DISPLAY_NAME"
    )
    founder_organization_slug: str = Field(
        default="st-joseph-county-indiana",
        min_length=1,
        validation_alias="CIVICOS_FOUNDER_ORGANIZATION_SLUG",
    )
    founder_organization_name: str = Field(
        default="St. Joseph County, Indiana",
        min_length=1,
        validation_alias="CIVICOS_FOUNDER_ORGANIZATION_NAME",
    )
    founder_token_ttl_seconds: int = Field(
        default=3600,
        ge=300,
        le=28800,
        validation_alias="CIVICOS_FOUNDER_TOKEN_TTL_SECONDS",
    )
    request_max_bytes: int = Field(
        default=1_000_000, ge=1_024, le=10_000_000, validation_alias="CIVICOS_API_MAX_REQUEST_BYTES"
    )
    rate_limit_per_minute: int = Field(
        default=120, ge=1, le=10_000, validation_alias="CIVICOS_API_RATE_LIMIT_PER_MINUTE"
    )
    metrics_token: str | None = Field(default=None, validation_alias="CIVICOS_METRICS_TOKEN")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    qdrant_url: str | None = Field(default=None, validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(
        default="civicos_documents", validation_alias="QDRANT_COLLECTION"
    )
    embedding_base_url: str | None = Field(default=None, validation_alias="EMBEDDING_BASE_URL")
    embedding_model: str | None = Field(default=None, validation_alias="EMBEDDING_MODEL")
    embedding_api_key: str | None = Field(default=None, validation_alias="EMBEDDING_API_KEY")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_model: str | None = Field(default=None, validation_alias="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    search_max_limit: int = Field(
        default=50, ge=1, le=100, validation_alias="CIVICOS_SEARCH_MAX_LIMIT"
    )
    assistant_retrieval_limit: int = Field(
        default=8, ge=1, le=20, validation_alias="CIVICOS_ASSISTANT_RETRIEVAL_LIMIT"
    )
    assistant_max_claims: int = Field(
        default=5, ge=1, le=10, validation_alias="CIVICOS_ASSISTANT_MAX_CLAIMS"
    )
    assistant_min_citations_per_claim: int = Field(
        default=1, ge=1, le=5, validation_alias="CIVICOS_ASSISTANT_MIN_CITATIONS_PER_CLAIM"
    )
    assistant_target_independent_sources: int = Field(
        default=2, ge=1, le=10, validation_alias="CIVICOS_ASSISTANT_TARGET_INDEPENDENT_SOURCES"
    )
    assistant_temperature: float = Field(
        default=0.0, ge=0, le=1, validation_alias="CIVICOS_ASSISTANT_TEMPERATURE"
    )
    assistant_high_confidence_threshold: float = Field(
        default=0.85, gt=0, le=1, validation_alias="CIVICOS_ASSISTANT_HIGH_CONFIDENCE_THRESHOLD"
    )
    assistant_medium_confidence_threshold: float = Field(
        default=0.6, gt=0, le=1, validation_alias="CIVICOS_ASSISTANT_MEDIUM_CONFIDENCE_THRESHOLD"
    )

    @model_validator(mode="after")
    def validate_confidence_thresholds(self) -> "Settings":
        if self.assistant_medium_confidence_threshold >= self.assistant_high_confidence_threshold:
            raise ValueError(
                "CIVICOS_ASSISTANT_MEDIUM_CONFIDENCE_THRESHOLD must be below "
                "CIVICOS_ASSISTANT_HIGH_CONFIDENCE_THRESHOLD"
            )
        if self.environment == "production":
            if self.auth_mode not in {"oidc", "founder_secret"}:
                raise ValueError("CIVICOS_AUTH_MODE must be oidc or founder_secret in production")
            if self.auth_mode == "oidc" and (
                not self.auth_issuer or not self.auth_audience or not self.auth_jwks_url
            ):
                raise ValueError("Production OIDC requires issuer, audience, and JWKS URL")
            if self.auth_mode == "founder_secret":
                if (
                    self.founder_auth_secret is None
                    or len(self.founder_auth_secret.get_secret_value()) < 32
                ):
                    raise ValueError(
                        "Founder-secret authentication requires CIVICOS_FOUNDER_AUTH_SECRET "
                        "with at least 32 characters"
                    )
            if "*" in self.allowed_hosts:
                raise ValueError("CIVICOS_ALLOWED_HOSTS must not contain * in production")
            if not self.metrics_token:
                raise ValueError("CIVICOS_METRICS_TOKEN must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""

    return Settings()
