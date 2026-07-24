from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class UserManagementError(RuntimeError):
    """Raised when tenant user administration cannot be completed safely."""


class UserManagementAccessError(PermissionError):
    """Raised when the active user is not a tenant administrator."""


class UserManagementNotFoundError(LookupError):
    """Raised when a tenant membership does not exist."""


@dataclass(frozen=True)
class AuthenticatedMembership:
    user_id: UUID
    organization_id: UUID
    role_key: str


@dataclass(frozen=True)
class ManagedUser:
    user_id: UUID
    external_subject: str
    email: str
    display_name: str
    role_key: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PostgresUserRepository:
    """Narrow access to identity membership functions installed by migration 0007."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def resolve_membership(
        self, *, external_subject: str, organization_id: UUID
    ) -> AuthenticatedMembership | None:
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            cursor = await connection.execute(
                "SELECT * FROM core.resolve_authenticated_principal(%s, %s)",
                (external_subject, organization_id),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return AuthenticatedMembership(
            user_id=UUID(str(row["user_id"])),
            organization_id=UUID(str(row["organization_id"])),
            role_key=str(row["role_key"]),
        )

    async def resolve_founder_organization(
        self, *, external_subject: str, organization_slug: str
    ) -> UUID | None:
        """Resolve only the configured active founder-admin membership."""

        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            cursor = await connection.execute(
                """
                SELECT organization.id
                FROM core.organizations AS organization
                JOIN core.organization_memberships AS membership
                  ON membership.organization_id = organization.id
                JOIN core.users AS member ON member.id = membership.user_id
                WHERE organization.slug = %s
                  AND organization.is_active
                  AND member.external_subject = %s
                  AND member.is_active
                  AND membership.is_active
                  AND membership.role_key = 'tenant_admin'
                """,
                (organization_slug, external_subject),
            )
            row = await cursor.fetchone()
        return UUID(str(row["id"])) if row is not None else None

    async def list_users(self, *, organization_id: UUID, user_id: UUID) -> list[ManagedUser]:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute("SELECT * FROM core.list_organization_users()")
            return [self._user_from_row(row) for row in await cursor.fetchall()]

    async def provision_user(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        external_subject: str,
        email: str,
        display_name: str,
        role_key: str,
    ) -> ManagedUser:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                "SELECT * FROM core.provision_organization_user(%s, %s, %s, %s)",
                (external_subject, email, display_name, role_key),
            )
            row = await self._one(cursor, "Could not provision organization user")
            return self._user_from_row(row)

    async def update_user(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        target_user_id: UUID,
        role_key: str,
        is_active: bool,
    ) -> ManagedUser:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                "SELECT * FROM core.update_organization_user(%s, %s, %s)",
                (target_user_id, role_key, is_active),
            )
            return self._user_from_row(await self._one(cursor, "Organization user was not found"))

    @asynccontextmanager
    async def _transaction(
        self, organization_id: UUID, user_id: UUID
    ) -> AsyncIterator[psycopg.AsyncConnection[dict[str, Any]]]:
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)", (str(organization_id),)
                )
                await connection.execute(
                    "SELECT set_config('app.user_id', %s, true)", (str(user_id),)
                )
                try:
                    yield connection
                except psycopg.errors.InsufficientPrivilege as error:
                    raise UserManagementAccessError(
                        "Tenant administrator role is required"
                    ) from error
                except psycopg.errors.NoDataFound as error:
                    raise UserManagementNotFoundError("Organization user was not found") from error
                except psycopg.Error as error:
                    raise UserManagementError(
                        "User management operation could not be completed"
                    ) from error

    @staticmethod
    async def _one(cursor: psycopg.AsyncCursor[dict[str, Any]], message: str) -> dict[str, Any]:
        row = await cursor.fetchone()
        if row is None:
            raise UserManagementNotFoundError(message)
        return row

    @staticmethod
    def _user_from_row(row: dict[str, Any]) -> ManagedUser:
        return ManagedUser(
            user_id=UUID(str(row["user_id"])),
            external_subject=str(row["external_subject"]),
            email=str(row["email"]),
            display_name=str(row["display_name"]),
            role_key=str(row["role_key"]),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
