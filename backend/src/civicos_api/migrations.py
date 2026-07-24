"""Apply immutable CivicOS SQL migrations during a production pre-deploy step."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path

import psycopg

DEFAULT_MIGRATIONS_DIRECTORY = Path("/app/database/migrations")
MIGRATION_LEDGER_TABLE = "public.civicos_schema_migrations"


class MigrationError(RuntimeError):
    """Raised when the migration history is missing, altered, or cannot be applied safely."""


def migration_paths(directory: Path = DEFAULT_MIGRATIONS_DIRECTORY) -> list[Path]:
    """Return the canonical, version-ordered forward migration files."""

    paths = sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.up.sql"))
    if not paths:
        raise MigrationError(f"No forward migrations found in {directory}")
    return paths


def migration_checksum(path: Path) -> str:
    """Return a stable digest used to prevent silently altered migration history."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_migrations(database_url: str, paths: Iterable[Path] | None = None) -> list[str]:
    """Apply every unapplied migration and return the versions applied in this run."""

    ordered_paths = list(paths) if paths is not None else migration_paths()
    if not ordered_paths:
        raise MigrationError("No migrations were supplied")

    applied_versions: list[str] = []
    with psycopg.connect(_psycopg_database_url(database_url), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.civicos_schema_migrations (
                    version text PRIMARY KEY,
                    checksum text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(f"SELECT version, checksum FROM {MIGRATION_LEDGER_TABLE}")
            applied: dict[str, str] = {
                str(version): str(checksum) for version, checksum in cursor.fetchall()
            }

            for path in ordered_paths:
                version = path.name
                checksum = migration_checksum(path)
                recorded_checksum = applied.get(version)
                if recorded_checksum is not None:
                    if recorded_checksum != checksum:
                        raise MigrationError(
                            f"Applied migration {version} does not match its recorded checksum"
                        )
                    continue

                cursor.execute(path.read_text(encoding="utf-8"))
                cursor.execute(
                    f"INSERT INTO {MIGRATION_LEDGER_TABLE} (version, checksum) VALUES (%s, %s)",
                    (version, checksum),
                )
                applied_versions.append(version)

    return applied_versions


def _psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    """Run the pre-deploy migration process using Railway's injected DATABASE_URL."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise MigrationError("DATABASE_URL must be set before migrations can run")
    applied_versions = apply_migrations(database_url)
    print(f"CivicOS migrations complete; applied {len(applied_versions)} migration(s).")


if __name__ == "__main__":
    main()
