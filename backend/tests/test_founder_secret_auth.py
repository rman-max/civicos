from uuid import UUID

import pytest
from pydantic import ValidationError

from civicos_api.auth import FounderSecretTokenVerifier
from civicos_api.config import Settings


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
