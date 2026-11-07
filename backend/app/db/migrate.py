import argparse
import hashlib
from pathlib import Path

from app.db.connection import connect

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATION_LOCK = 47071001


class MigrationError(RuntimeError):
    pass


def migrate(database_url: str | None = None, directory: Path = MIGRATIONS_DIR) -> list[str]:
    files = sorted(directory.glob("[0-9]*_*.sql"))
    if not files:
        raise MigrationError("No migration files found")
    migrations = [(path.stem, path.read_bytes()) for path in files]
    with connect(database_url) as connection:
        # The transaction lock also serializes first-time ledger creation.
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        applied = {row["version"]: row["checksum"] for row in connection.execute(
            "SELECT version, checksum FROM schema_migrations ORDER BY version"
        )}
        expected = [version for version, _ in migrations]
        if sorted(applied) != expected[:len(applied)]:
            raise MigrationError("Applied migrations must be an unchanged prefix of local migrations")
        for version, contents in migrations:
            if version in applied and applied[version] != hashlib.sha256(contents).hexdigest():
                raise MigrationError(f"Applied migration changed: {version}")
        executed = []
        for version, contents in migrations:
            if version in applied:
                continue
            connection.execute(contents.decode("utf-8-sig"))
            connection.execute(
                "INSERT INTO schema_migrations(version, checksum) VALUES (%s, %s)",
                (version, hashlib.sha256(contents).hexdigest()),
            )
            executed.append(version)
    return executed


def main() -> None:
    argparse.ArgumentParser(description="Apply versioned database migrations").parse_args()
    executed = migrate()
    print("Applied: " + ", ".join(executed) if executed else "Database is up to date")


if __name__ == "__main__":
    main()
