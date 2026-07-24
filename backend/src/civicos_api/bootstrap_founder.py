"""Provision the one temporary founder account during a Railway pre-deploy step.

This module intentionally runs only when the explicitly selected `founder_secret`
authentication mode is active. It is idempotent, creates no public account, and
refuses to silently mutate an existing identity with different attributes.
"""

from __future__ import annotations

import asyncio

import psycopg

from civicos_api.config import Settings, get_settings


class FounderBootstrapError(RuntimeError):
    """Raised when the configured founder identity cannot be provisioned safely."""


async def bootstrap_founder(settings: Settings) -> None:
    """Create the configured organization, founder user, and active admin membership."""

    if settings.auth_mode != "founder_secret":
        return
    if settings.database_url is None:
        raise FounderBootstrapError("DATABASE_URL must be configured before founder bootstrap")

    database_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        async with await psycopg.AsyncConnection.connect(database_url) as connection:
            async with connection.transaction():
                organization_id = await _organization_id(connection, settings)
                user_id = await _founder_user_id(connection, settings)
                await _ensure_membership(connection, organization_id, user_id)
    except psycopg.Error as error:
        raise FounderBootstrapError("Could not provision the temporary founder account") from error


async def _organization_id(
    connection: psycopg.AsyncConnection[tuple[object, ...]], settings: Settings
) -> str:
    cursor = await connection.execute(
        """
        INSERT INTO core.organizations (slug, name, organization_type, settings)
        VALUES (%s, %s, 'county', '{"country_code": "US", "state_code": "IN"}'::jsonb)
        ON CONFLICT (slug) DO NOTHING
        RETURNING id
        """,
        (settings.founder_organization_slug, settings.founder_organization_name),
    )
    row = await cursor.fetchone()
    if row is not None:
        return str(row[0])
    cursor = await connection.execute(
        "SELECT id, name, is_active FROM core.organizations WHERE slug = %s",
        (settings.founder_organization_slug,),
    )
    existing = await cursor.fetchone()
    if (
        existing is None
        or str(existing[1]) != settings.founder_organization_name
        or not bool(existing[2])
    ):
        raise FounderBootstrapError(
            "Existing founder organization does not match the configured identity"
        )
    return str(existing[0])


async def _founder_user_id(
    connection: psycopg.AsyncConnection[tuple[object, ...]], settings: Settings
) -> str:
    cursor = await connection.execute(
        """
        INSERT INTO core.users (external_subject, email, display_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (external_subject) DO NOTHING
        RETURNING id
        """,
        (settings.founder_external_subject, settings.founder_email, settings.founder_display_name),
    )
    row = await cursor.fetchone()
    if row is not None:
        return str(row[0])
    cursor = await connection.execute(
        "SELECT id, email, display_name, is_active FROM core.users WHERE external_subject = %s",
        (settings.founder_external_subject,),
    )
    existing = await cursor.fetchone()
    if (
        existing is None
        or str(existing[1]) != settings.founder_email
        or str(existing[2]) != settings.founder_display_name
        or not bool(existing[3])
    ):
        raise FounderBootstrapError("Existing founder user does not match the configured identity")
    return str(existing[0])


async def _ensure_membership(
    connection: psycopg.AsyncConnection[tuple[object, ...]], organization_id: str, user_id: str
) -> None:
    await connection.execute(
        """
        INSERT INTO core.organization_memberships (organization_id, user_id, role_key, is_active)
        VALUES (%s, %s, 'tenant_admin', true)
        ON CONFLICT (organization_id, user_id)
        DO UPDATE SET role_key = 'tenant_admin', is_active = true
        """,
        (organization_id, user_id),
    )


def main() -> None:
    """Run founder bootstrap after migrations, before the API starts accepting traffic."""

    settings = get_settings()
    asyncio.run(bootstrap_founder(settings))
    if settings.auth_mode == "founder_secret":
        print("Temporary founder account bootstrap complete.")


if __name__ == "__main__":
    main()
