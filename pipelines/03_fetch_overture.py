"""Step 03 — Overture Maps, queried in place over S3 with DuckDB.

Nothing is downloaded in bulk. DuckDB reads the remote GeoParquet, prunes on
the bbox struct columns, and writes only Ghana to a local GeoParquet file.
Buildings for the whole country come down in a few minutes on a decent
connection, versus hundreds of gigabytes for the full planet release.

The bbox gate is doing the real work here. Overture partitions its Parquet by
bbox, so the filter is a partition prune rather than a scan. Drop it and this
script will try to read the planet.

Usage:
    python pipelines/03_fetch_overture.py --theme buildings
    python pipelines/03_fetch_overture.py --theme places --city accra
    python pipelines/03_fetch_overture.py --list-releases
"""

from __future__ import annotations

import argparse

from common import GH, RAW, log, step
from common.db import duckdb_connect

# Pin the release. An unpinned "latest" makes results irreproducible, and the
# schema does change between releases.
DEFAULT_RELEASE = "2025-08-20.0"

S3_ROOT = "s3://overturemaps-us-west-2/release"

THEMES = {
    "buildings":      ("buildings",      "building"),
    "places":         ("places",         "place"),
    "transportation": ("transportation", "segment"),
    "divisions":      ("divisions",      "division_area"),
    "addresses":      ("addresses",      "address"),
    "base_water":     ("base",           "water"),
    "base_land_use":  ("base",           "land_use"),
}


def s3_path(theme: str, release: str) -> str:
    theme_dir, type_dir = THEMES[theme]
    return f"{S3_ROOT}/{release}/theme={theme_dir}/type={type_dir}/*"


def build_query(theme: str, bbox, release: str, limit: int | None) -> str:
    """Compose the extraction SQL.

    Two filters, both required:
      1. bbox struct comparison — the cheap partition prune
      2. ST_Intersects against the envelope — the exact test

    The bbox comparison uses the OVERLAP pattern. Containment would drop every
    feature that crosses the boundary, which for a national extract means
    losing every road that leaves the country and every coastal polygon.
    """
    w, s, e, n = bbox.as_tuple()
    path = s3_path(theme, release)

    # Columns differ per theme; select narrowly rather than SELECT *, because
    # Overture rows carry deep nested structs that bloat the output file.
    columns = {
        "buildings": """
            id,
            names.primary                        AS name,
            class,
            subtype,
            CAST(height AS DOUBLE)               AS height_m,
            CAST(num_floors AS INTEGER)          AS levels,
            sources[1].dataset                   AS source_dataset,
            geometry
        """,
        "places": """
            id,
            names.primary                        AS name,
            categories.primary                   AS category,
            confidence,
            addresses[1].locality                AS locality,
            geometry
        """,
        "transportation": """
            id,
            names.primary                        AS name,
            class,
            subtype,
            road_surface[1].value                AS surface,
            geometry
        """,
        "divisions": """
            id,
            names.primary                        AS name,
            subtype,
            class,
            country,
            region,
            geometry
        """,
        "base_water": """
            id, names.primary AS name, class, subtype, geometry
        """,
        "base_land_use": """
            id, names.primary AS name, class, subtype, geometry
        """,
        "addresses": """
            id, number, street, postcode, country, geometry
        """,
    }[theme]

    sql = f"""
    SELECT {columns}
    FROM read_parquet('{path}', filename = true, hive_partitioning = 1)
    WHERE bbox.xmax >= {w}      -- feature's right edge east of our left
      AND bbox.xmin <= {e}      -- feature's left edge west of our right
      AND bbox.ymax >= {s}      -- feature's top edge above our bottom
      AND bbox.ymin <= {n}      -- feature's bottom edge below our top
      AND ST_Intersects(geometry, ST_MakeEnvelope({w}, {s}, {e}, {n}))
    """
    if limit:
        sql += f"\n    LIMIT {limit}"
    return sql


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", default="buildings", choices=sorted(THEMES))
    parser.add_argument("--release", default=DEFAULT_RELEASE)
    parser.add_argument("--city", help="restrict to one city bbox instead of the country")
    parser.add_argument("--limit", type=int, help="cap rows, for a quick test run")
    parser.add_argument("--count-only", action="store_true",
                        help="count matching rows without writing anything")
    args = parser.parse_args()

    bbox = GH.city_bbox(args.city) if args.city else GH.bbox
    scope = args.city or "ghana"

    step("03", f"Overture {args.theme} ({scope}, release {args.release})")
    log.info("bbox %s", bbox.as_tuple())

    con = duckdb_connect()
    query = build_query(args.theme, bbox, args.release, args.limit)

    # Count first, always. A count is cheap and tells us whether the filter is
    # sane before committing to a long write. This is the same discipline the
    # GeoSQL skill enforces: validate, then extract.
    log.info("counting matching features...")
    count = con.execute(f"SELECT count(*) FROM ({query}) t").fetchone()[0]
    log.info("%s: %s features match", args.theme, f"{count:,}")

    if count == 0:
        raise SystemExit(
            "Zero features matched. Check the release string is valid and that "
            "the bbox filter uses the overlap pattern, not containment."
        )

    if args.count_only:
        return

    out = RAW / f"overture_{args.theme}_{scope}.parquet"
    log.info("writing %s", out.name)
    con.execute(f"""
        COPY ({query})
        TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """)

    # Post-write validation, in SQL, against the file we just produced.
    stats = con.execute(f"""
        SELECT
            count(*)                                        AS rows,
            count(*) FILTER (WHERE geometry IS NULL)        AS null_geom,
            min(ST_XMin(geometry))                          AS xmin,
            min(ST_YMin(geometry))                          AS ymin,
            max(ST_XMax(geometry))                          AS xmax,
            max(ST_YMax(geometry))                          AS ymax
        FROM read_parquet('{out}')
    """).fetchone()

    log.info("rows=%s  null geometry=%s", f"{stats[0]:,}", stats[1])
    log.info("extent  x %.4f..%.4f   y %.4f..%.4f", stats[2], stats[4], stats[3], stats[5])

    w, s, e, n = bbox.as_tuple()
    if not (stats[2] >= w - 0.5 and stats[4] <= e + 0.5
            and stats[3] >= s - 0.5 and stats[5] <= n + 0.5):
        raise SystemExit(
            "Extracted extent falls outside the requested bbox. The filter did "
            "not apply — do not load this file."
        )
    if stats[1]:
        raise SystemExit(f"{stats[1]} rows have null geometry. Investigate before loading.")

    log.info("saved %s (%.1f MB)", out.name, out.stat().st_size / 1e6)
    log.info("Step 03 complete.")


if __name__ == "__main__":
    main()
