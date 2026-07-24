#!/usr/bin/env sh

# Creates and verifies one PostgreSQL custom-format backup. The directory must be
# access-restricted and replicated by a separate job to encrypted off-site storage.

set -eu
umask 077

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${BACKUP_DIRECTORY:?BACKUP_DIRECTORY must be set}"

mkdir -p "$BACKUP_DIRECTORY"
backup_timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$BACKUP_DIRECTORY/civicos-postgres-$backup_timestamp.dump"

pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --no-privileges --file="$backup_path"
pg_restore --list "$backup_path" >/dev/null

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$backup_path" >"$backup_path.sha256"
else
  shasum -a 256 "$backup_path" >"$backup_path.sha256"
fi

printf '%s\n' "$backup_path"
