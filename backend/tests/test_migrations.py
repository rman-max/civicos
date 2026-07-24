from pathlib import Path

import pytest

from civicos_api.migrations import MigrationError, migration_checksum, migration_paths


def test_migration_paths_returns_only_ordered_forward_migrations(tmp_path: Path) -> None:
    (tmp_path / "0002_second.up.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "0001_first.up.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0001_first.down.sql").write_text("SELECT 1;", encoding="utf-8")

    assert [path.name for path in migration_paths(tmp_path)] == [
        "0001_first.up.sql",
        "0002_second.up.sql",
    ]


def test_migration_paths_rejects_an_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(MigrationError, match="No forward migrations"):
        migration_paths(tmp_path)


def test_migration_checksum_changes_when_migration_contents_change(tmp_path: Path) -> None:
    migration = tmp_path / "0001_example.up.sql"
    migration.write_text("SELECT 1;", encoding="utf-8")
    original_checksum = migration_checksum(migration)

    migration.write_text("SELECT 2;", encoding="utf-8")

    assert migration_checksum(migration) != original_checksum
