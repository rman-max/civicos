"""Private founder-intelligence API, limited to tenant administrators."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class FounderIntelligenceAccessError(PermissionError):
    """Raised when a caller is not an authorized founder-console administrator."""


class FounderIntelligenceUnavailableError(RuntimeError):
    """Raised when a founder-intelligence operation cannot complete safely."""


@dataclass(frozen=True)
class FounderOpportunity:
    id: UUID
    signal_id: UUID
    signal_type: str
    title: str
    what_happened: str
    why_it_matters: str
    where_money_may_be: str
    who_might_pay: list[str]
    action_to_take: str
    urgency: str
    score: int
    evidence: list[dict[str, Any]]
    affected_organizations: list[str]
    source_url: str | None
    document_title: str
    discovered_at: datetime


@dataclass(frozen=True)
class FounderSignal:
    id: UUID
    signal_type: str
    title: str
    summary: str
    why_it_matters: str
    commercial_significance: int
    confidence_score: float
    evidence: list[dict[str, Any]]
    affected_organizations: list[str]
    potential_customer_segments: list[str]
    source_url: str | None
    discovered_at: datetime


@dataclass(frozen=True)
class FounderWatchlist:
    id: UUID
    watch_type: str
    name: str
    normalized_term: str
    criteria: dict[str, Any]
    is_active: bool
    match_count: int
    latest_match_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class FounderBrief:
    id: UUID
    briefing_date: date
    content: dict[str, Any]
    generated_at: datetime


class PostgresFounderIntelligenceRepository:
    """A thin adapter over tenant-admin security-definer database functions."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def list_opportunities(
        self, *, organization_id: UUID, user_id: UUID, limit: int
    ) -> list[FounderOpportunity]:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                "SELECT * FROM founder.list_opportunities(%s)", (limit,)
            )
            return [self._opportunity_from_row(row) for row in await cursor.fetchall()]

    async def list_signals(
        self, *, organization_id: UUID, user_id: UUID, limit: int
    ) -> list[FounderSignal]:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute("SELECT * FROM founder.list_signals(%s)", (limit,))
            return [self._signal_from_row(row) for row in await cursor.fetchall()]

    async def list_watchlists(
        self, *, organization_id: UUID, user_id: UUID
    ) -> list[FounderWatchlist]:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute("SELECT * FROM founder.list_watchlists()")
            return [self._watchlist_from_row(row) for row in await cursor.fetchall()]

    async def create_watchlist(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        watch_type: str,
        name: str,
        term: str,
        criteria: dict[str, Any],
    ) -> FounderWatchlist:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                "SELECT * FROM founder.create_watchlist(%s, %s, %s, %s)",
                (watch_type, name, term, Jsonb(criteria)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise FounderIntelligenceUnavailableError("Could not save founder watchlist")
        return self._watchlist_from_row(row)

    async def latest_brief(self, *, organization_id: UUID, user_id: UUID) -> FounderBrief | None:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute("SELECT * FROM founder.latest_daily_brief()")
            row = await cursor.fetchone()
        return self._brief_from_row(row) if row is not None else None

    @asynccontextmanager
    async def _transaction(
        self, organization_id: UUID, user_id: UUID
    ) -> AsyncIterator[psycopg.AsyncConnection[dict[str, Any]]]:
        try:
            async with await psycopg.AsyncConnection.connect(
                self._database_url, row_factory=dict_row
            ) as connection:
                async with connection.transaction():
                    await connection.execute(
                        "SELECT set_config('app.organization_id', %s, true)",
                        (str(organization_id),),
                    )
                    await connection.execute(
                        "SELECT set_config('app.user_id', %s, true)", (str(user_id),)
                    )
                    yield connection
        except psycopg.errors.InsufficientPrivilege as error:
            raise FounderIntelligenceAccessError(
                "Founder Intelligence requires a tenant administrator role"
            ) from error
        except psycopg.Error as error:
            raise FounderIntelligenceUnavailableError(
                "Founder Intelligence storage is unavailable"
            ) from error

    @staticmethod
    def _opportunity_from_row(row: dict[str, Any]) -> FounderOpportunity:
        return FounderOpportunity(
            id=UUID(str(row["opportunity_id"])),
            signal_id=UUID(str(row["signal_id"])),
            signal_type=str(row["signal_type"]),
            title=str(row["title"]),
            what_happened=str(row["what_happened"]),
            why_it_matters=str(row["why_it_matters"]),
            where_money_may_be=str(row["where_money_may_be"]),
            who_might_pay=list(row["who_might_pay"]),
            action_to_take=str(row["action_to_take"]),
            urgency=str(row["urgency"]),
            score=int(row["score"]),
            evidence=list(row["evidence"]),
            affected_organizations=list(row["affected_organizations"]),
            source_url=str(row["source_url"]) if row["source_url"] else None,
            document_title=str(row["document_title"]),
            discovered_at=row["discovered_at"],
        )

    @staticmethod
    def _signal_from_row(row: dict[str, Any]) -> FounderSignal:
        return FounderSignal(
            id=UUID(str(row["id"])),
            signal_type=str(row["signal_type"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            why_it_matters=str(row["why_it_matters"]),
            commercial_significance=int(row["commercial_significance"]),
            confidence_score=float(row["confidence_score"]),
            evidence=list(row["evidence"]),
            affected_organizations=list(row["affected_organizations"]),
            potential_customer_segments=list(row["potential_customer_segments"]),
            source_url=str(row["source_url"]) if row["source_url"] else None,
            discovered_at=row["discovered_at"],
        )

    @staticmethod
    def _watchlist_from_row(row: dict[str, Any]) -> FounderWatchlist:
        return FounderWatchlist(
            id=UUID(str(row["id"])),
            watch_type=str(row["watch_type"]),
            name=str(row["name"]),
            normalized_term=str(row["normalized_term"]),
            criteria=dict(row["criteria"]),
            is_active=bool(row["is_active"]),
            match_count=int(row["match_count"]),
            latest_match_at=row["latest_match_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _brief_from_row(row: dict[str, Any]) -> FounderBrief:
        return FounderBrief(
            id=UUID(str(row["id"])),
            briefing_date=row["briefing_date"],
            content=dict(row["content"]),
            generated_at=row["generated_at"],
        )
