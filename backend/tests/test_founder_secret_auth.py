import asyncio
import logging
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from civicos_api.auth import AuthenticationError, Authenticator, FounderSecretTokenVerifier
from civicos_api.config import Settings
from civicos_api.users import PostgresUserRepository


class ListLogHandler(logging.Handler):
    """Capture a logger with a non-propagating application parent in unit tests."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def founder_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "CIVICOS_ENVIRONMENT": "production",
        "CIVICOS_AUTH_MODE": "founder_secret",
        "CIVICOS_FOUNDER_AUTH_SECRET": "a" * 64,
        "CIVICOS_ALLOWED_HOSTS": ["api.example.test"],
        "CIVICOS_METRICS_TOKEN": "metrics-token",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_founder_secret_mode_accepts_production_configuration_without_oidc() -> None:
    settings = founder_settings()

    assert settings.auth_mode == "founder_secret"
    assert settings.auth_issuer is None


def test_founder_secret_mode_rejects_a_short_secret() -> None:
    with pytest.raises(ValidationError, match="CIVICOS_FOUNDER_AUTH_SECRET"):
        founder_settings(CIVICOS_FOUNDER_AUTH_SECRET="short")


def test_founder_tokens_are_short_lived_and_bound_to_the_configured_founder() -> None:
    verifier = FounderSecretTokenVerifier(founder_settings())
    organization_id = UUID("10000000-0000-0000-0000-000000000001")

    token, expires_in = verifier.issue(organization_id)
    verified = verifier.verify(f"Bearer {token}")

    assert expires_in == 3600
    assert verified.external_subject == "civicos-founder"
    assert verified.organization_id == organization_id


def test_founder_login_logs_only_safe_secret_comparison_diagnostics() -> None:
    configured_secret = "a" * 64
    authenticator = Authenticator(
        founder_settings(CIVICOS_FOUNDER_AUTH_SECRET=configured_secret),
        cast(PostgresUserRepository, object()),
    )

    log_handler = ListLogHandler()
    auth_logger = logging.getLogger("civicos.api.auth")
    auth_logger.addHandler(log_handler)
    try:
        with pytest.raises(AuthenticationError, match="founder secret is invalid"):
            asyncio.run(authenticator.login_founder("not-the-configured-secret"))
    finally:
        auth_logger.removeHandler(log_handler)

    diagnostic = "\n".join(log_handler.messages)
    assert "configured_secret_length=64" in diagnostic
    assert "submitted_secret_length=25" in diagnostic
    assert "sha256_hashes_match=False" in diagnostic
    assert configured_secret not in diagnostic
    assert "not-the-configured-secret" not in diagnostic
