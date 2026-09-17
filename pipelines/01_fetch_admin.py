"""Step 01 — administrative boundaries.

Regions and districts are the backbone of everything else: every other table
gets a region_id and a district_id, so if this step is wrong, every join
downstream is wrong.

Source priority, best first:
  1. Ghana Statistical Service (authoritative, post-2019, needs a data request)
  2. GRID3 Ghana (CC BY 4.0, current, downloadable)
  3. GADM 4.1 (non-commercial, districts lag the 2018-19 reorganisation)

We start on GADM so the stack runs today, and the loader is written so that
swapping in GSS later changes this file only.

Usage:
    python pipelines/01_fetch_admin.py
    python pipelines/01_fetch_admin.py --source grid3
"""

from __future__ import annotations

import argparse
import sys

import geopandas as gpd
import requests

from common import GH, RAW, log, source, step
from common.validate import check_gdf

GADM_LAYERS = {0: "ADM_ADM_0", 1: "ADM_ADM_1", 2: "ADM_ADM_2"}


def download(url: str, dest, *, chunk: int = 1 << 20) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        log.info("already downloaded: %s", dest.name)
        return
    log.info("downloading %s", url)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for block in r.iter_content(chunk_size=chunk):
                fh.write(block)
        tmp.rename(dest)
    log.info("saved %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)


def fetch_gadm() -> None:
    src = source("admin_gadm")
    gpkg = RAW / "gadm41_GHA.gpkg"
    download(src["url"], gpkg)

    for level, layer in GADM_LAYERS.items():
        gdf = gpd.read_file(gpkg, layer=layer)
        gdf = gdf.to_crs(4326)

        # GADM ships a lot of columns nobody needs. Keep the ones that
        # actually identify the unit, and normalise the names now rather than
        # in every downstream query.
        rename = {
            "GID_0": "gid_0", "NAME_0": "name_0",
            "GID_1": "gid_1", "NAME_1": "name_1",
            "GID_2": "gid_2", "NAME_2": "name_2",
            "TYPE_2": "type_2", "ENGTYPE_2": "engtype_2",
        }
        gdf = gdf.rename(columns={k: v for k, v in rename.items() if k in gdf.columns})
        keep = [c for c in rename.values() if c in gdf.columns] + ["geometry"]
        gdf = gdf[keep]

        # GADM polygons occasionally self-intersect at simplified coastlines.
        gdf["geometry"] = gdf.geometry.make_valid()

        expected = {0: 1, 1: GH.expected_regions, 2: 200}[level]
        check_gdf(
            gdf,
            f"GADM level {level}",
            min_rows=expected if level < 2 else 200,
            geom_types={"Polygon", "MultiPolygon"},
        )

        out = RAW / f"admin_level_{level}.gpkg"
        gdf.to_file(out, driver="GPKG", layer=f"admin_{level}")
        log.info("level %d: %d features -> %s", level, len(gdf), out.name)

        if level == 1 and len(gdf) != GH.expected_regions:
            log.warning(
                "GADM returned %d regions, Ghana has %d since 2019. GADM 4.1 "
                "predates the new regions in places. Treat level 1 as "
                "provisional until the GSS boundaries are loaded.",
                len(gdf), GH.expected_regions,
            )


def fetch_grid3() -> None:
    """GRID3 is CC BY 4.0 and current, but the download is behind a portal
    search rather than a stable URL, so this step guides rather than fetches."""
    src = source("admin_grid3")
    log.warning(
        "GRID3 has no stable direct download URL. Fetch the Ghana boundary "
        "and settlement-extent layers manually from %s, drop the GeoPackage "
        "in %s, then rerun with --source local.",
        src["url"], RAW,
    )
    sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="gadm",
                        choices=["gadm", "grid3", "local"],
                        help="which boundary source to fetch")
    args = parser.parse_args()

    step("01", f"Administrative boundaries ({args.source})")

    if args.source == "gadm":
        fetch_gadm()
    elif args.source == "grid3":
        fetch_grid3()
    else:
        log.info("using boundary files already in %s", RAW)

    log.info("Step 01 complete. Next: 02_fetch_osm.py")


if __name__ == "__main__":
    main()
