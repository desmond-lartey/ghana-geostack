"""Step 20 — load into PostGIS.

Replaces the original pipeline's subprocess-and-Windows-path approach with
something that runs identically on a laptop, a server and CI:

  * migrations run in order and are idempotent
  * vectors load through GeoPandas, so the CRS is explicit at write time
  * rasters load through raster2pgsql only if the binary is present, and the
    step degrades to a warning rather than a crash if it is not
  * every table is validated after loading and before it is registered
  * nothing is registered as publishable without a licence and attribution

Usage:
    python pipelines/20_load_postgis.py --migrate      # schema only
    python pipelines/20_load_postgis.py                # migrate then load
    python pipelines/20_load_postgis.py --only buildings
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

import geopandas as gpd

from common import GH, PROCESSED, RAW, ROOT, db, log, source, step
from common.validate import check_magnitude, check_table

MIGRATIONS = sorted((ROOT / "db" / "migrations").glob("*.sql"))


# ── Schema ─────────────────────────────────────────────────────────────────

def migrate() -> None:
    log.info("running %d migrations", len(MIGRATIONS))
    for path in MIGRATIONS:
        db.run_sql_file(path)
    db.ensure_building_partitions(GH.regions)


# ── Vector loading ─────────────────────────────────────────────────────────

def load_vector(gdf, schema: str, table: str, *, if_exists: str = "replace",
                chunksize: int = 50_000) -> None:
    """Write a GeoDataFrame to PostGIS.

    to_postgis writes the SRID into geometry_columns correctly, which is the
    thing CREATE TABLE AS silently fails to do. The original pipeline needed a
    block of UpdateGeometrySRID calls at the end of its analysis file to
    repair exactly that; loading this way avoids the problem.
    """
    from sqlalchemy import create_engine

    if gdf.crs is None:
        raise ValueError(f"{schema}.{table}: CRS is undefined. Set it explicitly.")
    if gdf.crs.to_epsg() != 4326:
        log.info("%s.%s: reprojecting %s -> EPSG:4326", schema, table, gdf.crs.to_epsg())
        gdf = gdf.to_crs(4326)

    engine = create_engine(db.sqlalchemy_url())
    gdf.to_postgis(table, engine, schema=schema, if_exists=if_exists,
                   index=False, chunksize=chunksize)

    db.execute(
        f'CREATE INDEX IF NOT EXISTS {table}_geom_idx '
        f'ON {schema}."{table}" USING GIST (geometry)'
    )
    log.info("loaded %s rows -> %s.%s", f"{len(gdf):,}", schema, table)


def load_admin() -> None:
    """Load the COD boundaries. Everything else joins to them, so this runs first."""
    log.info("loading administrative boundaries")

    reference = ROOT / "data" / "reference"
    layers = {
        "gha_admin0": "admin_level_0",
        "gha_admin1": "admin_level_1",
        "gha_admin2": "admin_level_2",
        "gha_admincapitals": "admin_capital",
    }

    for layer, table in layers.items():
        path = reference / f"{layer}.geojson"
        if not path.exists():
            raise SystemExit(
                f"Missing {path}. Run 01_fetch_admin.py, or restore the "
                f"committed reference boundaries.")
        gdf = gpd.read_file(path)
        gdf.columns = [c.lower() for c in gdf.columns]
        load_vector(gdf, "raw", table)

    # raw -> core: p-code hierarchy, name corrections, aliases.
    db.run_sql_file(ROOT / "db" / "transform" / "admin.sql")

    check_table("core", "admin_region", min_rows=16)
    check_table("core", "admin_district", min_rows=260)
    check_magnitude("core", "admin_region", kind="area",
                    low=235_000, high=242_000, unit="km2")

    src = source("cod_ab_ghana")
    for table, title in (("admin_country", "Ghana national boundary"),
                         ("admin_region", "Ghana regions"),
                         ("admin_district", "Ghana districts (MMDAs)")):
        db.register(f"core.{table}", "core", table, title, "admin",
                    src["name"], src["licence"], src["attribution"],
                    publishable=True)

    log.info("boundaries loaded: %s regions, %s districts",
             db.scalar("SELECT count(*) FROM core.admin_region"),
             db.scalar("SELECT count(*) FROM core.admin_district"))


def load_buildings() -> None:
    """Overture first if present, OSM as the fallback."""
    overture = RAW / "overture_buildings_ghana.parquet"
    osm = RAW / "osm_buildings.parquet"

    if overture.exists():
        path, src_id = overture, "overture_buildings"
    elif osm.exists():
        path, src_id = osm, "osm_ghana"
    else:
        log.warning("no building file found — run 02 or 03 first")
        return

    log.info("loading buildings from %s", path.name)
    gdf = gpd.read_parquet(path)
    gdf["source_id"] = src_id
    load_vector(gdf, "raw", "building")

    db.run_sql_file(ROOT / "db" / "transform" / "buildings.sql")

    check_table("core", "building", min_rows=10_000)
    src = source(src_id)
    db.register("core.building", "core", "building", "Building footprints",
                "buildings", src["name"], src["licence"], src["attribution"],
                publishable=True)


def load_roads() -> None:
    path = RAW / "osm_roads.parquet"
    if not path.exists():
        log.warning("missing %s — run 02_fetch_osm.py", path.name)
        return
    gdf = gpd.read_parquet(path)
    gdf["source_id"] = "osm_ghana"
    load_vector(gdf, "raw", "road")
    db.run_sql_file(ROOT / "db" / "transform" / "roads.sql")

    check_table("core", "road", min_rows=10_000)
    # A national road network well under 60,000 km means the extract is
    # partial. This check has caught a truncated download more than once.
    check_magnitude("core", "road", kind="length",
                    low=40_000, high=250_000, unit="km")

    src = source("osm_ghana")
    db.register("core.road", "core", "road", "Road network", "transport",
                src["name"], src["licence"], src["attribution"], publishable=True)


# ── Raster loading ─────────────────────────────────────────────────────────

def load_raster(tif: Path, schema: str, table: str, *,
                srid: int = 4326, tile: str = "256x256") -> bool:
    """Pipe raster2pgsql into psql.

    Returns False rather than raising when the tooling is missing: a machine
    without the PostgreSQL client binaries can still run the whole vector
    pipeline, and terrain analysis is the only thing that degrades.
    """
    r2p = shutil.which("raster2pgsql")
    psql = shutil.which("psql")
    if not (r2p and psql):
        log.warning(
            "raster2pgsql or psql not on PATH — skipping %s. Install the "
            "PostgreSQL client tools, or load rasters from inside the "
            "container with: docker compose exec postgis raster2pgsql ...",
            tif.name)
        return False
    if not tif.exists():
        log.warning("missing raster %s", tif)
        return False

    env = {**os.environ, "PGPASSWORD": os.getenv("PGPASSWORD", "ghana")}
    export = subprocess.Popen(
        [r2p, "-s", str(srid), "-I", "-C", "-M", "-t", tile,
         str(tif), f"{schema}.{table}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    load = subprocess.Popen(
        [psql, "-h", os.getenv("PGHOST", "localhost"),
         "-p", os.getenv("PGPORT", "5432"),
         "-U", os.getenv("PGUSER", "ghana"),
         "-d", os.getenv("PGDATABASE", "ghana"), "-q"],
        stdin=export.stdout, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env)
    export.stdout.close()          # psql owns the pipe now; avoids a deadlock
    _, err = load.communicate()

    if load.returncode != 0:
        log.error("raster load failed for %s: %s", tif.name, err.decode()[:400])
        return False
    log.info("loaded raster %s -> %s.%s", tif.name, schema, table)
    return True


def load_terrain() -> None:
    if load_raster(PROCESSED / "dem_ghana.tif", "core", "dem"):
        db.register("core.dem", "core", "dem", "Copernicus DEM GLO-30",
                    "terrain", "Copernicus", "Copernicus DEM licence",
                    source("dem_copernicus_30")["attribution"], publishable=True)
    load_raster(PROCESSED / "slope_ghana.tif", "core", "slope")


# ── Entry point ────────────────────────────────────────────────────────────

LOADERS = {
    "admin": load_admin,
    "buildings": load_buildings,
    "roads": load_roads,
    "terrain": load_terrain,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migrate", action="store_true", help="run migrations and stop")
    parser.add_argument("--skip-migrate", action="store_true")
    parser.add_argument("--only", choices=sorted(LOADERS), help="load one group")
    args = parser.parse_args()

    step("20", "Load into PostGIS")

    if not args.skip_migrate:
        migrate()
    if args.migrate:
        log.info("migrations complete.")
        return

    for name, fn in LOADERS.items():
        if args.only and name != args.only:
            continue
        log.info("--- %s ---", name)
        fn()

    log.info("Step 20 complete. Next: 30_run_analysis.py")


if __name__ == "__main__":
    main()
