from __future__ import annotations

from enum import StrEnum

import psycopg


class FeedbackCategory(StrEnum):
    BUG = "bug"
    IDEA = "idea"
    SOURCE = "source"
    GENERAL = "general"


class BetaAnalyticsEventName(StrEnum):
    PAGE_VIEW = "beta_page_view"
    DEMO_STARTED = "demo_started"
    EXAMPLE_NOTEBOOK_OPENED = "example_notebook_opened"
    FEEDBACK_OPENED = "feedback_opened"
    FEEDBACK_SUBMITTED = "feedback_submitted"


class BetaSurface(StrEnum):
    LANDING = "landing"
    DEMO = "demo"
    NOTEBOOK = "notebook"
    FEEDBACK = "feedback"


class PublicBetaUnavailableError(RuntimeError):
    """Raised when voluntary beta telemetry storage is unavailable."""


class PublicBetaRepository:
    """Stores opt-in beta feedback and anonymous, first-party product events."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def submit_feedback(
        self,
        *,
        category: FeedbackCategory,
        message: str,
        contact_email: str | None,
        page_path: str,
    ) -> None:
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
                await connection.execute(
                    "SELECT core.submit_public_beta_feedback(%s, %s, %s, %s)",
                    (category, message, contact_email, page_path),
                )
        except psycopg.Error as error:
            raise PublicBetaUnavailableError("Feedback storage is unavailable") from error

    async def record_event(
        self, *, event_name: BetaAnalyticsEventName, page_path: str, surface: BetaSurface | None
    ) -> None:
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
                await connection.execute(
                    "SELECT core.record_public_beta_analytics_event(%s, %s, %s)",
                    (event_name, page_path, surface),
                )
        except psycopg.Error as error:
            raise PublicBetaUnavailableError("Analytics storage is unavailable") from error
