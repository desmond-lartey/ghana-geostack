"""Database access for both engines.

PostGIS is the authoritative store. DuckDB is the portable analytics engine -
same data, no server, reads the GeoParquet exports directly. Any query that
can run in both should produce identical numbers, and the QC suite checks that.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import EXPORTS, ROOT
from .log import log


# ── PostGIS ────────────────────────────────────────────────────────────────

def dsn() -> str:
    """Connection string from the environment, with docker-compose defaults."""
    return (
        f"host={os.getenv('PGHOST', 'localhost')} "
        f"port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'ghana')} "
        f"user={os.getenv('PGUSER', 'ghana')} "
        f"password={os.getenv('PGPASSWORD', 'ghana')}"
    )


def sqlalchemy_url() -> str:
    return (
        f"postgresql+psycopg://{os.getenv('PGUSER', 'ghana')}:"
        f"{os.getenv('PGPASSWORD', 'ghana')}@"
        f"{os.getenv('PGHOST', 'localhost')}:"
        f"{os.getenv('PGPORT', '5432')}/"
        f"{os.getenv('PGDATABASE', 'ghana')}"
    )


@contextmanager
def connect() -> Iterator[Any]:
    """Yield a psycopg connection, committing on clean exit."""
    import psycopg

    conn = psycopg.connect(dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql: str, params: tuple | None = None) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)


def fetch(sql: str, params: tuple | None = None) -> list[tuple]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def scalar(sql: str, params: tuple | None = None):
    rows = fetch(sql, params)
    return rows[0][0] if rows else None


def run_sql_file(path: str | Path) -> None:
    """Run a .sql file through psql so that \\set, \\gset and \\i all work.

    psycopg cannot interpret psql meta-commands, and the QC file relies on
    them, so shelling out to psql is the correct call rather than a shortcut.
    """
    import subprocess

    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path

    env = {**os.environ, "PGPASSWORD": os.getenv("PGPASSWORD", "ghana")}
    cmd = [
        "psql",
        "-h", os.getenv("PGHOST", "localhost"),
        "-p", os.getenv("PGPORT", "5432"),
        "-U", os.getenv("PGUSER", "ghana"),
        "-d", os.getenv("PGDATABASE", "ghana"),
        "-v", "ON_ERROR_STOP=1",
        "-f", str(path),
    ]
    log.info("psql -f %s", path.relative_to(ROOT) if ROOT in path.parents else path)
    result = subprocess.run(cmd, env=env, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{path.name} failed with exit code {result.returncode}")


def register(
    dataset_id: str,
    schema: str,
    table: str,
    title: str,
    theme: str,
    source_name: str,
    licence: str,
    attribution: str,
    publishable: bool = False,
) -> None:
    """Record a loaded table in meta.dataset. Call this at the end of every load."""
    execute(
        "SELECT meta.register(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (dataset_id, schema, table, title, theme,
         source_name, licence, attribution, publishable),
    )
    log.info("registered %s.%s as %s", schema, table, dataset_id)


def ensure_building_partitions(regions: list[str]) -> None:
    """Create one core.building partition per region.

    Partitioning by region keeps every regional query touching a single
    partition, which matters once Google Open Buildings pushes the table past
    ten million rows.
    """
    with connect() as conn, conn.cursor() as cur:
        for region in regions:
            slug = region.lower().replace(" ", "_")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS core.building_{slug}
                PARTITION OF core.building FOR VALUES IN (%s)
                """,
                (region,),
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS building_{slug}_geom_idx "
                f"ON core.building_{slug} USING GIST (geom)"
            )
    log.info("building partitions ready for %d regions", len(regions))


# ── DuckDB ─────────────────────────────────────────────────────────────────

def duckdb_connect(database: str | Path | None = None, read_only: bool = False):
    """Open DuckDB with the spatial stack loaded.

    Passing None gives an in-memory database, which is the right default for
    remote GeoParquet queries - nothing needs to be persisted.
    """
    import duckdb

    con = duckdb.connect(str(database) if database else ":memory:", read_only=read_only)
    for ext in ("spatial", "httpfs", "parquet", "json"):
        try:
            con.execute(f"INSTALL {ext};")
        except Exception:
            pass  # already installed, or no network - LOAD will tell us
        con.execute(f"LOAD {ext};")

    # H3 is a community extension, so it is optional rather than assumed.
    try:
        con.execute("INSTALL h3 FROM community; LOAD h3;")
    except Exception:
        log.warning("DuckDB h3 extension unavailable - hex rollups will be skipped")

    con.execute("SET s3_region='us-west-2';")
    return con


def duckdb_lakehouse(read_only: bool = True):
    """Open the local DuckDB file with views over every GeoParquet export.

    This is the zero-install path: clone the repo, pull the exports, query.
    No Postgres, no Docker, works on a laptop with patchy connectivity - which
    is the realistic condition for a lot of fieldwork in Ghana.
    """
    con = duckdb_connect(EXPORTS / "ghana.duckdb", read_only=read_only)
    return con


def attach_postgres(con) -> None:
    """Attach the live PostGIS database to a DuckDB session.

    Lets one query join a GeoParquet export against a live Postgres table,
    which is the usual way to check that the two engines agree.
    """
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(f"ATTACH '{dsn()}' AS pg (TYPE postgres, READ_ONLY);")
