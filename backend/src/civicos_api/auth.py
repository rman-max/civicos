from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

import jwt
from jwt import InvalidTokenError, PyJWKClient

from civicos_api.users import AuthenticatedMembership, PostgresUserRepository

if TYPE_CHECKING:
    from civicos_api.config import Settings


# Application logging configures the `civicos` namespace, not the package name.
logger = logging.getLogger("civicos.api.auth")


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


class TokenVerifier(Protocol):
    """Verifies a bearer token into the identity claims CivicOS needs at its edge."""

    def verify(self, authorization_header: str | None) -> VerifiedToken: ...


class FounderSecretTokenVerifier:
    """Verifies the temporary, single-founder tokens issued by CivicOS itself.

    This mode deliberately has no registration, account recovery, or user-discovery
    surface. Its issuer and audience are private application constants so it cannot
    be confused with an eventual OIDC token.
    """

    issuer = "civicos-founder-secret"
    audience = "civicos-founder"

    def __init__(self, settings: Settings) -> None:
        if settings.founder_auth_secret is None:
            raise ValueError("Founder-secret authentication requires CIVICOS_FOUNDER_AUTH_SECRET")
        self._secret = settings.founder_auth_secret.get_secret_value()
        self._external_subject = settings.founder_external_subject
        self._organization_slug = settings.founder_organization_slug
        self._ttl_seconds = settings.founder_token_ttl_seconds

    @property
    def secret(self) -> str:
        """Return the in-memory secret only for constant-time login comparison."""

        return self._secret

    @property
    def external_subject(self) -> str:
        return self._external_subject

    @property
    def organization_slug(self) -> str:
        return self._organization_slug

    def verify(self, authorization_header: str | None) -> VerifiedToken:
        token = _bearer_token(authorization_header)
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "organization_id"]},
            )
        except InvalidTokenError as error:
            raise AuthenticationError("The bearer token is invalid or expired") from error
        if claims.get("sub") != self._external_subject:
            raise AuthenticationError("The bearer token is not authorized for this founder account")
        if claims.get("organization_slug") != self._organization_slug:
            raise AuthenticationError("The bearer token is not authorized for this organization")
        organization_claim = claims.get("organization_id")
        if not isinstance(organization_claim, str):
            raise AuthenticationError("The bearer token does not contain a tenant claim")
        try:
            organization_id = UUID(organization_claim)
        except ValueError as error:
            raise AuthenticationError("The bearer token tenant claim is invalid") from error
        return VerifiedToken(
            external_subject=self._external_subject, organization_id=organization_id
        )

    def issue(self, organization_id: UUID) -> tuple[str, int]:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self._ttl_seconds)
        token = jwt.encode(
            {
                "sub": self._external_subject,
                "organization_id": str(organization_id),
                "organization_slug": self._organization_slug,
                "iss": self.issuer,
                "aud": self.audience,
                "iat": now,
                "exp": expires_at,
            },
            self._secret,
            algorithm="HS256",
        )
        return token, self._ttl_seconds


class Authenticator:
    """Combines token verification with the authoritative CivicOS membership check."""

    def __init__(self, settings: Settings, user_repository: PostgresUserRepository | None) -> None:
        self._token_verifier: TokenVerifier | None
        if settings.auth_mode == "oidc":
            self._token_verifier = OidcTokenVerifier(settings)
        elif settings.auth_mode == "founder_secret":
            self._token_verifier = FounderSecretTokenVerifier(settings)
        else:
            self._token_verifier = None
        self._user_repository = user_repository

    async def authenticate(self, authorization_header: str | None) -> Principal:
        if self._token_verifier is None or self._user_repository is None:
            raise AuthenticationError("Bearer authentication is not configured")
        verified = self._token_verifier.verify(authorization_header)
        membership = await self._user_repository.resolve_membership(
            external_subject=verified.external_subject,
            organization_id=verified.organization_id,
        )
        if membership is None:
            raise AuthenticationError("The authenticated user has no active tenant membership")
        return _principal_from_membership(verified, membership)

    async def login_founder(self, supplied_secret: str) -> tuple[str, int]:
        """Exchange the configured founder secret for one short-lived bearer token."""

        if (
            not isinstance(self._token_verifier, FounderSecretTokenVerifier)
            or self._user_repository is None
        ):
            raise AuthenticationError("Founder-secret authentication is not configured")
        configured_secret = self._token_verifier.secret
        submitted_hash = hashlib.sha256(supplied_secret.encode("utf-8")).digest()
        configured_hash = hashlib.sha256(configured_secret.encode("utf-8")).digest()
        hashes_match = secrets.compare_digest(submitted_hash, configured_hash)
        # Temporary production diagnostic. Do not log either secret or either digest.
        logger.info(
            "founder_login_secret_comparison configured_secret_length=%d "
            "submitted_secret_length=%d sha256_hashes_match=%s",
            len(configured_secret),
            len(supplied_secret),
            hashes_match,
        )
        if not hashes_match:
            raise AuthenticationError("The founder secret is invalid")
        organization_id = await self._user_repository.resolve_founder_organization(
            external_subject=self._token_verifier.external_subject,
            organization_slug=self._token_verifier.organization_slug,
        )
        if organization_id is None:
            raise AuthenticationError("The founder account is not provisioned or active")
        return self._token_verifier.issue(organization_id)


def _principal_from_membership(
    verified: VerifiedToken, membership: AuthenticatedMembership
) -> Principal:
    return Principal(
        user_id=membership.user_id,
        organization_id=membership.organization_id,
        role_key=membership.role_key,
        external_subject=verified.external_subject,
    )


def _bearer_token(authorization_header: str | None) -> str:
    if authorization_header is None:
        raise AuthenticationError("A bearer token is required")
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Authorization must use the Bearer scheme")
    return token


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
