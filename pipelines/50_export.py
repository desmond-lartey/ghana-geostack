"""Step 50 — export.

Turns the PostGIS database into artefacts that work without PostGIS:

  * GeoParquet per layer — the interchange format. Reads in QGIS, DuckDB,
    GeoPandas, R, Python, ArcGIS Pro and the browser.
  * ghana.duckdb — one file, with views over every layer. Clone the repo,
    open the file, run SQL. No server, no Docker, works offline. This is the
    path that matters most for anyone working outside a data centre.
  * PMTiles — a single-file tile archive that a static site can serve.
  * attribution.md — the licence and credit line for everything exported.

Only datasets registered as publishable in meta.dataset are exported. That
gate is the whole point: it makes it structurally difficult to publish data
whose licence has not been read.

Usage:
    python pipelines/50_export.py
    python pipelines/50_export.py --layer core.building
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess

import geopandas as gpd

from common import EXPORTS, ROOT, log, step
from common import db


def publishable_layers() -> list[tuple[str, str, str, str]]:
    """(schema, table, title, attribution) for everything cleared to publish."""
    return db.fetch(
        """
        SELECT schema_name, table_name, title, attribution
        FROM meta.dataset
        WHERE publishable
        ORDER BY schema_name, table_name
        """
    )


def export_geoparquet(schema: str, table: str) -> int:
    """Write one table to GeoParquet."""
    from sqlalchemy import create_engine

    engine = create_engine(db.sqlalchemy_url())
    geom_col = db.scalar(
        "SELECT f_geometry_column FROM geometry_columns "
        "WHERE f_table_schema = %s AND f_table_name = %s LIMIT 1",
        (schema, table),
    )
    if geom_col is None:
        log.warning("%s.%s has no geometry column — skipped", schema, table)
        return 0

    gdf = gpd.read_postgis(
        f'SELECT * FROM {schema}."{table}"', engine, geom_col=geom_col)
    out = EXPORTS / f"{schema}.{table}.parquet"
    gdf.to_parquet(out, compression="zstd", geometry_encoding="WKB",
                   write_covering_bbox=True)
    log.info("%s.%s -> %s (%s rows, %.1f MB)",
             schema, table, out.name, f"{len(gdf):,}", out.stat().st_size / 1e6)
    return len(gdf)


def build_duckdb(layers) -> None:
    """Assemble the single-file DuckDB database over the Parquet exports.

    Views rather than copies, so the file stays small and the Parquet
    remains the source of truth. Anyone who wants a fully self-contained
    database can materialise the views with CREATE TABLE AS.
    """
    path = EXPORTS / "ghana.duckdb"
    if path.exists():
        path.unlink()

    con = db.duckdb_connect(path)
    con.execute("CREATE SCHEMA IF NOT EXISTS ghana;")

    for schema, table, title, _ in layers:
        parquet = EXPORTS / f"{schema}.{table}.parquet"
        if not parquet.exists():
            continue
        view = f"{schema}_{table}"
        con.execute(
            f"CREATE OR REPLACE VIEW ghana.{view} AS "
            f"SELECT * FROM read_parquet('{parquet.name}');"
        )
        con.execute(f"COMMENT ON VIEW ghana.{view} IS '{title.replace(chr(39), '')}';")
        log.info("duckdb view ghana.%s", view)

    # A catalogue inside the database, so someone handed only this file can
    # still find out what is in it and who to credit.
    con.execute("""
        CREATE OR REPLACE TABLE ghana.catalogue (
            layer text, title text, attribution text, licence text, rows bigint
        );
    """)
    for schema, table, title, attribution in layers:
        licence = db.scalar(
            "SELECT licence FROM meta.dataset WHERE schema_name=%s AND table_name=%s",
            (schema, table))
        count = db.scalar(f'SELECT count(*) FROM {schema}."{table}"')
        con.execute(
            "INSERT INTO ghana.catalogue VALUES (?, ?, ?, ?, ?)",
            [f"{schema}_{table}", title, attribution, licence, count])

    con.close()
    log.info("built %s (%.1f MB)", path.name, path.stat().st_size / 1e6)


def build_pmtiles(layers) -> None:
    """Build a PMTiles archive with tippecanoe, if it is installed.

    PMTiles is a single file that a static host can serve over range requests,
    so a full national basemap can live on GitHub Pages with no tile server.
    """
    if not shutil.which("tippecanoe"):
        log.warning(
            "tippecanoe not installed — skipping PMTiles. Install it to "
            "publish tiles from static hosting: "
            "https://github.com/felt/tippecanoe")
        return

    geojson_dir = EXPORTS / "geojson"
    geojson_dir.mkdir(exist_ok=True)
    inputs = []

    for schema, table, _, _ in layers:
        parquet = EXPORTS / f"{schema}.{table}.parquet"
        if not parquet.exists():
            continue
        gdf = gpd.read_parquet(parquet)
        # Tiles carry only what a map needs. Everything else stays in the API.
        drop = [c for c in gdf.columns
                if c.endswith("_at") or c in ("source_checksum",)]
        gdf = gdf.drop(columns=drop, errors="ignore")
        path = geojson_dir / f"{schema}_{table}.geojson"
        gdf.to_file(path, driver="GeoJSON")
        inputs += ["-L", f"{schema}_{table}:{path}"]

    if not inputs:
        return

    out = EXPORTS / "ghana.pmtiles"
    cmd = [
        "tippecanoe", "-o", str(out), "--force",
        "-zg",                        # guess max zoom from feature density
        "--drop-densest-as-needed",   # keep tiles under the size limit
        "--extend-zooms-if-still-dropping",
        "--attribution", "Ghana GeoStack — see attribution.md",
        *inputs,
    ]
    log.info("running tippecanoe")
    subprocess.run(cmd, check=True)
    log.info("built %s (%.1f MB)", out.name, out.stat().st_size / 1e6)


def write_attribution(layers) -> None:
    """The credit line. Required by ODbL and CC-BY, and simply correct."""
    lines = [
        "# Attribution",
        "",
        "Data published by Ghana GeoStack. Every layer below carries the "
        "licence and credit required by its source. If you use these files, "
        "reproduce the relevant lines.",
        "",
    ]
    for schema, table, title, attribution in layers:
        licence = db.scalar(
            "SELECT licence FROM meta.dataset WHERE schema_name=%s AND table_name=%s",
            (schema, table))
        lines += [f"## {title}", "",
                  f"- Layer: `{schema}.{table}`",
                  f"- Licence: {licence}",
                  f"- Credit: {attribution}", ""]

    (EXPORTS / "attribution.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("wrote attribution.md covering %d layers", len(layers))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", help="export one layer as schema.table")
    parser.add_argument("--skip-tiles", action="store_true")
    args = parser.parse_args()

    step("50", "Export")

    # Refuse to export from a build whose QC failed.
    last = db.fetch("SELECT passed, finished_at FROM meta.qc_run ORDER BY id DESC LIMIT 1")
    if not last:
        raise SystemExit("No QC run recorded. Run 40_qc.py before exporting.")
    if not last[0][0]:
        raise SystemExit(
            "The most recent QC run failed. Fix the errors and re-run QC "
            "before exporting — the export gate exists precisely to stop a "
            "broken build reaching the web.")

    layers = publishable_layers()
    if args.layer:
        schema, table = args.layer.split(".", 1)
        layers = [l for l in layers if (l[0], l[1]) == (schema, table)]
        if not layers:
            raise SystemExit(
                f"{args.layer} is not registered as publishable. Check its "
                f"licence, then set publishable = true in meta.dataset.")

    log.info("%d publishable layers", len(layers))
    for schema, table, _, _ in layers:
        export_geoparquet(schema, table)

    build_duckdb(layers)
    if not args.skip_tiles:
        build_pmtiles(layers)
    write_attribution(layers)

    manifest = {
        "layers": [{"schema": s, "table": t, "title": ti, "attribution": a}
                   for s, t, ti, a in layers],
        "files": sorted(p.name for p in EXPORTS.iterdir() if p.is_file()),
    }
    (EXPORTS / "manifest.json").write_text(json.dumps(manifest, indent=2))

    log.info("Step 50 complete. Exports in %s", EXPORTS)


if __name__ == "__main__":
    main()
