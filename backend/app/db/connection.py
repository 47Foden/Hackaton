import os

import psycopg
from psycopg.rows import dict_row


class DatabaseConfigurationError(RuntimeError):
    pass


def connect(database_url: str | None = None) -> psycopg.Connection:
    """Use as a context manager: commit on success, rollback on error, then close."""
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise DatabaseConfigurationError("DATABASE_URL is required")
    return psycopg.connect(url, connect_timeout=5, row_factory=dict_row)
