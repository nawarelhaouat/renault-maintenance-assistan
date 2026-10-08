import os
from contextlib import contextmanager
from functools import lru_cache

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

DSN = os.getenv("DATABASE_URL", "postgresql://gmao:gmao@localhost:5432/gmao")


@lru_cache(maxsize=1)
def _pool() -> ThreadedConnectionPool:
    return ThreadedConnectionPool(1, 10, DSN)


@contextmanager
def _cursor():
    pool = _pool()
    conn = pool.getconn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:   # commit si OK, rollback sinon
            yield cur
    finally:
        pool.putconn(conn, close=bool(conn.closed))


def query(sql: str, params=None) -> list[dict]:
    with _cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def execute(sql: str, params=None) -> list[dict]:
    """INSERT / UPDATE / DELETE ; retourne les lignes de RETURNING s'il y en a."""
    with _cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()] if cur.description else []