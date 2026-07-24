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


def test_core_set_updated_at_prerequisite_precedes_every_consumer() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    names = [path.name for path in migration_paths(repository_root / "database" / "migrations")]
    prerequisite_index = names.index("0001_core_set_updated_at_compatibility.up.sql")

    for consumer in (
        "0002_autonomous_discovery.up.sql",
        "0003_knowledge_graph.up.sql",
        "0004_hybrid_search.up.sql",
    ):
        assert prerequisite_index < names.index(consumer)
