"""Step 05 — zonal statistics.

Summarises any raster onto any boundary set. This is the single operation
behind most of what this platform is for:

    population per district      sum of WorldPop
    built-up share per district  sum of GHSL
    mean temperature per zone    mean of Landsat LST
    rainfall per catchment       sum of CHIRPS over HydroSHEDS basins
    tree cover per district      mean of Hansen tree cover

All the same thing: take the pixels inside a polygon, reduce them to a number,
attach it to the polygon. Writing it once means the population workflow and the
urban heat workflow are the same workflow with different inputs.

Output is a CSV keyed on p-code, written to `data/exports/`. The viewer reads
that directly, so a result computed here is queryable in the browser without a
database. `--load` also writes it into PostGIS.

Usage:
    python pipelines/05_zonal_stats.py data/raw/worldpop_population_ghana.tif \\
        --zones district --stat sum --column population --load

    python pipelines/05_zonal_stats.py data/raw/landsat_lst_accra.tif \\
        --zones district --stat mean --column lst_c --scale 0.00341802 --offset -124.15

    python pipelines/05_zonal_stats.py data/raw/ghsl_built_ghana.tif \\
        --zones district --stat sum --column built_m2
"""

from __future__ import annotations

import argparse
from pathlib import Path

from common import EXPORTS, ROOT, db, log, step

ZONE_SOURCES = {
    "region": ("data/reference/gha_admin1.geojson", "adm1_pcode", "adm1_name"),
    "district": ("data/reference/gha_admin2.geojson", "adm2_pcode", "adm2_name"),
    "country": ("data/reference/gha_admin0.geojson", "adm0_pcode", "adm0_name"),
}

STATS = ("sum", "mean", "median", "min", "max", "count", "std")


def load_zones(name: str):
    """Boundaries as a GeoDataFrame, with the key and label columns identified."""
    import geopandas as gpd

    if name in ZONE_SOURCES:
        path, key, label = ZONE_SOURCES[name]
        zones = gpd.read_file(ROOT / path)
    else:
        # Any other vector file: a HydroSHEDS basin set, an urban boundary, a
        # catchment someone drew themselves.
        path = Path(name)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise SystemExit(
                f"{name} is neither a built-in zone set "
                f"({', '.join(ZONE_SOURCES)}) nor a file that exists."
            )
        zones = gpd.read_file(path)
        key = next((c for c in ("HYBAS_ID", "hybas_id", "id", "shapeID")
                    if c in zones.columns), zones.columns[0])
        label = next((c for c in ("name", "shapeName", "place_name")
                      if c in zones.columns), key)

    log.info("%d zones from %s, keyed on %s", len(zones), name, key)
    return zones, key, label


def zonal(raster_path: Path, zones, key: str, label: str,
          stat: str, scale: float, offset: float, nodata: float | None):
    """Reduce the pixels inside each polygon to one number.

    Uses rasterio's own masking rather than rasterstats, which is one fewer
    dependency for a step many people will run on a laptop.
    """
    import numpy as np
    import rasterio
    from rasterio.mask import mask

    rows = []

    with rasterio.open(raster_path) as src:
        log.info("raster %s, CRS %s, %d x %d",
                 raster_path.name, src.crs, src.width, src.height)

        # The zones meet the raster in its own CRS, not the other way round:
        # reprojecting a few hundred polygons is free, reprojecting a national
        # raster is not.
        if zones.crs != src.crs:
            log.info("reprojecting zones %s -> %s", zones.crs, src.crs)
            zones = zones.to_crs(src.crs)

        fill = nodata if nodata is not None else src.nodata

        reducers = {
            "sum": np.sum, "mean": np.mean, "median": np.median,
            "min": np.min, "max": np.max, "std": np.std,
            "count": lambda v: v.size,
        }

        for _, zone in zones.iterrows():
            try:
                clipped, _ = mask(src, [zone.geometry], crop=True,
                                  all_touched=False, filled=True,
                                  nodata=fill if fill is not None else 0)
            except ValueError:
                # The polygon does not overlap the raster at all.
                rows.append({key: zone[key], "name": zone[label],
                             stat: None, "pixels": 0})
                continue

            values = clipped[0].astype("float64")
            if fill is not None:
                values = values[values != fill]
            values = values[np.isfinite(values)]

            if values.size == 0:
                rows.append({key: zone[key], "name": zone[label],
                             stat: None, "pixels": 0})
                continue

            values = values * scale + offset

            rows.append({
                key: zone[key],
                "name": zone[label],
                stat: float(reducers[stat](values)),
                "pixels": int(values.size),
            })

    return rows


def load_into_postgis(frame, key: str, column: str, zones: str) -> None:
    """Write the result back onto the boundary table it was computed from."""
    table = {"region": "admin_region", "district": "admin_district"}.get(zones)
    if not table:
        log.warning("--load applies only to the built-in region and district zones")
        return

    from sqlalchemy import create_engine

    engine = create_engine(db.sqlalchemy_url())
    staging = f"zonal_{column}"
    frame.to_sql(staging, engine, schema="analysis", if_exists="replace", index=False)

    db.execute(f"""
        ALTER TABLE core.{table} ADD COLUMN IF NOT EXISTS {column} double precision;
        UPDATE core.{table} t
        SET {column} = z."{column}"
        FROM analysis.{staging} z
        WHERE t.id = z."{key}";
    """)
    updated = db.scalar(f"SELECT count(*) FROM core.{table} WHERE {column} IS NOT NULL")
    log.info("core.%s.%s set for %s rows", table, column, updated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raster", type=Path, help="GeoTIFF to summarise")
    parser.add_argument("--zones", default="district",
                        help="region, district, country, or a path to a vector file")
    parser.add_argument("--stat", default="sum", choices=STATS)
    parser.add_argument("--column", help="name for the output column; defaults to the stat")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="multiply pixel values by this before reducing")
    parser.add_argument("--offset", type=float, default=0.0,
                        help="add this after scaling. Landsat ST_B10 to Celsius "
                             "is --scale 0.00341802 --offset -124.15")
    parser.add_argument("--nodata", type=float, help="override the raster's nodata value")
    parser.add_argument("--out", type=Path, help="output CSV; defaults to data/exports/")
    parser.add_argument("--load", action="store_true",
                        help="also write the result into PostGIS")
    args = parser.parse_args()

    raster = args.raster if args.raster.is_absolute() else ROOT / args.raster
    if not raster.exists():
        raise SystemExit(
            f"{raster} does not exist.\n"
            "Fetch it first, for example:\n"
            "  python pipelines/04_fetch_gee.py worldpop_population"
        )

    step("05", f"Zonal {args.stat} of {raster.name} by {args.zones}")

    try:
        import geopandas  # noqa: F401
        import rasterio  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            f"{exc.name} is needed for zonal statistics.\n"
            "  conda env create -f environment.yml\n"
            "is the reliable route; pip needs GDAL installed first."
        ) from None

    zones, key, label = load_zones(args.zones)
    rows = zonal(raster, zones, key, label, args.stat,
                 args.scale, args.offset, args.nodata)

    column = args.column or args.stat
    if column != args.stat:
        for row in rows:
            row[column] = row.pop(args.stat)

    import pandas as pd

    frame = pd.DataFrame(rows)
    covered = int(frame[column].notna().sum())

    log.info("%d of %d zones have a value", covered, len(frame))
    if covered == 0:
        raise SystemExit(
            "No zone overlapped the raster. Usually the raster covers a "
            "different area than the zones, or its CRS is wrong."
        )
    if covered < len(frame):
        log.warning(
            "%d zones had no overlapping pixels. Expected if the raster was "
            "fetched for one city; nationally it means a gap.",
            len(frame) - covered)

    out = args.out or (EXPORTS / f"{raster.stem}_{args.zones}_{args.stat}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    log.info("wrote %s", out)

    # A summary worth reading: a total wrong by an order of magnitude is
    # obvious here and invisible in a CSV.
    numeric = frame[column].dropna()
    log.info("total   %s", f"{numeric.sum():,.1f}")
    log.info("mean    %s", f"{numeric.mean():,.1f}")
    log.info("range   %s .. %s", f"{numeric.min():,.1f}", f"{numeric.max():,.1f}")

    print()
    print(frame.nlargest(min(10, len(frame)), column)[["name", column]]
          .to_string(index=False))

    if args.load:
        load_into_postgis(frame, key, column, args.zones)

    log.info("Step 05 complete.")


if __name__ == "__main__":
    main()
