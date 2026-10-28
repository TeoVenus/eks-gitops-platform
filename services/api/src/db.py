from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Runs on every startup. IF NOT EXISTS makes it safe to run again.
SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url        TEXT        NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS check_results (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    target_id   BIGINT      NOT NULL REFERENCES targets (id) ON DELETE CASCADE,
    checked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    up          BOOLEAN     NOT NULL,
    status_code INTEGER,
    response_ms INTEGER,
    error       TEXT
);

CREATE INDEX IF NOT EXISTS check_results_target_id_checked_at
    ON check_results (target_id, checked_at DESC);
"""


def create_pool(database_url: str) -> ConnectionPool:
    """Open a pool of database connections and make sure the table exists."""
    pool = ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row},  # rows come back as dicts: {"id": 1, "url": ...}
        open=False,
    )
    pool.open(wait=True, timeout=10)  # fail fast at startup if the database is unreachable
    with pool.connection() as conn:
        conn.execute(SCHEMA)
    return pool
