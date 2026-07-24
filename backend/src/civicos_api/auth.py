from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

import jwt
from jwt import InvalidTokenError, PyJWKClient

from civicos_api.users import AuthenticatedMembership, PostgresUserRepository

if TYPE_CHECKING:
    from civicos_api.config import Settings


class AuthenticationError(PermissionError):
    """Raised when an API request lacks a valid, authorized bearer identity."""


@dataclass(frozen=True)
class VerifiedToken:
    external_subject: str
    organization_id: UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    organization_id: UUID
    role_key: str
    external_subject: str


class OidcTokenVerifier:
    """Verifies signed OIDC access tokens against the configured issuer JWKS."""

    def __init__(self, settings: Settings) -> None:
        if not settings.auth_jwks_url or not settings.auth_issuer or not settings.auth_audience:
            raise ValueError("OIDC settings must include issuer, audience, and JWKS URL")
        self._issuer = settings.auth_issuer
        self._audience = settings.auth_audience
        self._organization_claim = settings.auth_organization_claim
        self._jwks_client = PyJWKClient(str(settings.auth_jwks_url))

    def verify(self, authorization_header: str | None) -> VerifiedToken:
        if authorization_header is None:
            raise AuthenticationError("A bearer token is required")
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthenticationError("Authorization must use the Bearer scheme")
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=str(self._issuer),
                options={"require": ["exp", "iat", "sub"]},
            )
        except InvalidTokenError as error:
            raise AuthenticationError("The bearer token is invalid or expired") from error
        subject = claims.get("sub")
        organization_claim = claims.get(self._organization_claim)
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError("The bearer token does not contain a usable subject")
        if not isinstance(organization_claim, str):
            raise AuthenticationError("The bearer token does not contain a tenant claim")
        try:
            organization_id = UUID(organization_claim)
        except ValueError as error:
            raise AuthenticationError("The bearer token tenant claim is invalid") from error
        return VerifiedToken(external_subject=subject, organization_id=organization_id)


class Authenticator:
    """Combines token verification with the authoritative CivicOS membership check."""

    def __init__(self, settings: Settings, user_repository: PostgresUserRepository | None) -> None:
        self._token_verifier = OidcTokenVerifier(settings) if settings.auth_mode == "oidc" else None
        self._user_repository = user_repository

    async def authenticate(self, authorization_header: str | None) -> Principal:
        if self._token_verifier is None or self._user_repository is None:
            raise AuthenticationError("OIDC authentication is not configured")
        verified = self._token_verifier.verify(authorization_header)
        membership = await self._user_repository.resolve_membership(
            external_subject=verified.external_subject,
            organization_id=verified.organization_id,
        )
        if membership is None:
            raise AuthenticationError("The authenticated user has no active tenant membership")
        return _principal_from_membership(verified, membership)


def _principal_from_membership(
    verified: VerifiedToken, membership: AuthenticatedMembership
) -> Principal:
    return Principal(
        user_id=membership.user_id,
        organization_id=membership.organization_id,
        role_key=membership.role_key,
        external_subject=verified.external_subject,
    )


def principal_headers(
    principal: Principal, headers: list[tuple[bytes, bytes]]
) -> list[tuple[bytes, bytes]]:
    """Replace client-controlled legacy scope headers with verified identity values."""
    protected = {
        b"x-civicos-organization-id",
        b"x-civicos-user-id",
        b"x-civicos-role",
    }
    sanitized = [(name, value) for name, value in headers if name.lower() not in protected]
    sanitized.extend(
        [
            (b"x-civicos-organization-id", str(principal.organization_id).encode()),
            (b"x-civicos-user-id", str(principal.user_id).encode()),
            (b"x-civicos-role", principal.role_key.encode()),
        ]
    )
    return sanitized


def problem_response(status_code: int, detail: str) -> dict[str, Any]:
    return {
        "type": "https://civicos.org/problems/authentication",
        "title": "Authentication failed",
        "status": status_code,
        "detail": detail,
    }
