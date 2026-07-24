from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class BriefingAccessError(PermissionError):
    """Raised when the caller is not an active organization member."""


class BriefingNotFoundError(LookupError):
    """Raised when a briefing is not delivered to the requesting user."""


@dataclass(frozen=True)
class BriefingSubscription:
    id: UUID
    delivery_channel: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DailyBriefing:
    id: UUID
    briefing_date: date
    content: dict[str, Any]
    generated_at: datetime
    delivery_status: str
    delivered_at: datetime
    read_at: datetime | None


class PostgresBriefingRepository:
    """User-scoped access to durable in-app daily briefings."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def subscribe(self, *, organization_id: UUID, user_id: UUID) -> BriefingSubscription:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO research.briefing_subscriptions (organization_id, user_id, delivery_channel)
                VALUES (%s, %s, 'in_app')
                ON CONFLICT (organization_id, user_id, delivery_channel)
                DO UPDATE SET is_active = true
                RETURNING id, delivery_channel, is_active, created_at, updated_at
                """,
                (organization_id, user_id),
            )
            return self._subscription_from_row(
                await self._one(cursor, "Could not create subscription")
            )

    async def unsubscribe(
        self, *, organization_id: UUID, user_id: UUID, subscription_id: UUID
    ) -> BriefingSubscription:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                """
                UPDATE research.briefing_subscriptions
                SET is_active = false
                WHERE organization_id = %s AND user_id = %s AND id = %s
                RETURNING id, delivery_channel, is_active, created_at, updated_at
                """,
                (organization_id, user_id, subscription_id),
            )
            return self._subscription_from_row(
                await self._one(cursor, "Subscription was not found")
            )

    async def list_briefings(
        self, *, organization_id: UUID, user_id: UUID, limit: int
    ) -> list[DailyBriefing]:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                """
                SELECT briefing.id, briefing.briefing_date, briefing.content, briefing.generated_at,
                  delivery.status AS delivery_status, delivery.delivered_at, delivery.read_at
                FROM research.daily_briefing_deliveries AS delivery
                JOIN research.briefing_subscriptions AS subscription
                  ON subscription.organization_id = delivery.organization_id
                  AND subscription.id = delivery.subscription_id
                JOIN research.daily_briefings AS briefing
                  ON briefing.organization_id = delivery.organization_id AND briefing.id = delivery.briefing_id
                WHERE delivery.organization_id = %s AND subscription.user_id = %s
                ORDER BY briefing.briefing_date DESC, briefing.id
                LIMIT %s
                """,
                (organization_id, user_id, limit),
            )
            return [self._briefing_from_row(row) for row in await cursor.fetchall()]

    async def mark_read(
        self, *, organization_id: UUID, user_id: UUID, briefing_id: UUID
    ) -> DailyBriefing:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                """
                WITH updated AS (
                  UPDATE research.daily_briefing_deliveries AS delivery
                  SET status = 'read', read_at = coalesce(read_at, now())
                  FROM research.briefing_subscriptions AS subscription
                  WHERE delivery.organization_id = %s
                    AND delivery.briefing_id = %s
                    AND subscription.organization_id = delivery.organization_id
                    AND subscription.id = delivery.subscription_id
                    AND subscription.user_id = %s
                  RETURNING delivery.status, delivery.delivered_at, delivery.read_at
                )
                SELECT briefing.id, briefing.briefing_date, briefing.content, briefing.generated_at,
                  updated.status AS delivery_status, updated.delivered_at, updated.read_at
                FROM updated
                JOIN research.daily_briefings AS briefing
                  ON briefing.organization_id = %s AND briefing.id = %s
                """,
                (organization_id, briefing_id, user_id, organization_id, briefing_id),
            )
            return self._briefing_from_row(await self._one(cursor, "Briefing was not found"))

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
                cursor = await connection.execute(
                    """
                    SELECT 1
                    FROM core.organization_memberships AS membership
                    JOIN core.users AS member ON member.id = membership.user_id
                    WHERE membership.organization_id = %s AND membership.user_id = %s AND member.is_active
                    """,
                    (organization_id, user_id),
                )
                if await cursor.fetchone() is None:
                    raise BriefingAccessError("User is not an active organization member")
                yield connection

    @staticmethod
    async def _one(cursor: psycopg.AsyncCursor[dict[str, Any]], message: str) -> dict[str, Any]:
        row = await cursor.fetchone()
        if row is None:
            raise BriefingNotFoundError(message)
        return row

    @staticmethod
    def _subscription_from_row(row: dict[str, Any]) -> BriefingSubscription:
        return BriefingSubscription(
            id=UUID(str(row["id"])),
            delivery_channel=str(row["delivery_channel"]),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _briefing_from_row(row: dict[str, Any]) -> DailyBriefing:
        return DailyBriefing(
            id=UUID(str(row["id"])),
            briefing_date=row["briefing_date"],
            content=dict(row["content"]),
            generated_at=row["generated_at"],
            delivery_status=str(row["delivery_status"]),
            delivered_at=row["delivered_at"],
            read_at=row["read_at"],
        )
