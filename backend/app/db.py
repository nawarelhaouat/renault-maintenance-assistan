import os

import psycopg2
from psycopg2.extras import RealDictCursor

DSN = os.getenv("DATABASE_URL", "postgresql://gmao:gmao@localhost:5432/gmao")


def query(sql: str, params=None) -> list[dict]:
    with psycopg2.connect(DSN) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]