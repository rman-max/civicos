"""Idempotently install the approved St. Joseph County connector configuration."""

from __future__ import annotations

from pathlib import Path

import psycopg

SEED_PATH = Path("/app/database/seeds/st_joseph_county_indiana.sql")


def apply_st_joseph_seed(database_url: str) -> None:
    """Run the reviewed source configuration before a worker claims discovery jobs."""

    if not SEED_PATH.is_file():
        raise RuntimeError(f"St. Joseph County seed is missing from the worker image: {SEED_PATH}")
    normalized_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(normalized_url, autocommit=True) as connection:
        connection.execute(SEED_PATH.read_text(encoding="utf-8"))
