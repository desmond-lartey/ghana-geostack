"""Step 01 - administrative boundaries.

Loads the Ghana Common Operational Dataset (COD-AB): 16 regions and 260
districts, each carrying an OCHA p-code. P-codes are the join key used
throughout this database, so this step runs before every other load.

The converted boundaries are committed under data/reference/, which means
this step needs no network access and the repository is usable immediately
after cloning. Passing --shapefiles re-converts from an original COD
shapefile bundle, for when a newer version is published.

Usage:
    python pipelines/01_fetch_admin.py
    python pipelines/01_fetch_admin.py --shapefiles ~/Downloads/gha_admin_boundaries_shp
    python pipelines/01_fetch_admin.py --verify
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import GH, ROOT, log, source, step

REFERENCE = ROOT / "data" / "reference"

# Layer name in the bundle -> the raw table it becomes.
LAYERS = {
    "gha_admin0": "admin_level_0",
    "gha_admin1": "admin_level_1",
    "gha_admin2": "admin_level_2",
    "gha_admincapitals": "admin_capital",
}

EXPECTED = {
    "gha_admin0": 1,
    "gha_admin1": 16,
    "gha_admin2": 260,
}


def convert_bundle(directory: Path) -> None:
    """Convert a COD shapefile bundle to GeoJSON in data/reference/."""
    from tools.shp2geojson import ShapefileError, convert

    shapefiles = [directory / f"{name}.shp" for name in LAYERS]
    missing = [p.name for p in shapefiles if not p.exists()]
    if missing:
        raise SystemExit(
            f"Missing layers in {directory}: {', '.join(missing)}. "
            f"Expected a COD-AB bundle containing {', '.join(LAYERS)}.")

    REFERENCE.mkdir(parents=True, exist_ok=True)
    for shp in shapefiles:
        try:
            out = convert(shp, REFERENCE / f"{shp.stem}.geojson")
        except ShapefileError as exc:
            raise SystemExit(f"{shp.name}: {exc}") from exc
        log.info("converted %s (%.1f MB)", out.name, out.stat().st_size / 1e6)


def verify() -> dict[str, dict]:
    """Check the reference boundaries before anything is loaded from them.

    Confirms feature counts, p-code format, hierarchy consistency and that the
    geometry falls inside Ghana. Raises rather than returning on failure: a
    wrong boundary set corrupts every table that joins to it.
    """
    summary: dict[str, dict] = {}
    west, south, east, north = GH.bbox.as_tuple()

    for layer in LAYERS:
        path = REFERENCE / f"{layer}.geojson"
        if not path.exists():
            raise SystemExit(
                f"Missing {path}. Convert a COD bundle with --shapefiles, or "
                f"restore the committed reference boundaries.")

        data = json.loads(path.read_text(encoding="utf-8"))
        features = data["features"]

        expected = EXPECTED.get(layer)
        if expected and len(features) != expected:
            raise SystemExit(
                f"{layer}: {len(features)} features, expected {expected}. "
                f"A region count of 10 means a pre-2019 boundary set.")

        xs, ys = [], []
        for feature in features:
            geom = feature["geometry"]
            polygons = (geom["coordinates"] if geom["type"] == "MultiPolygon"
                        else [geom["coordinates"]] if geom["type"] == "Polygon"
                        else [[[geom["coordinates"]]]])
            for polygon in polygons:
                for ring in polygon:
                    for point in ring:
                        xs.append(point[0])
                        ys.append(point[1])

        if not (west - 0.5 <= min(xs) and max(xs) <= east + 0.5
                and south - 0.5 <= min(ys) and max(ys) <= north + 0.5):
            raise SystemExit(
                f"{layer}: geometry falls outside Ghana "
                f"(x {min(xs):.3f}..{max(xs):.3f}, y {min(ys):.3f}..{max(ys):.3f}). "
                f"Check coordinate order and CRS.")

        summary[layer] = {
            "features": len(features),
            "extent": [round(min(xs), 4), round(min(ys), 4),
                       round(max(xs), 4), round(max(ys), 4)],
        }
        log.info("%-18s %4d features   extent %s", layer, len(features),
                 summary[layer]["extent"])

    # Hierarchy: every district p-code must begin with a region p-code.
    regions = {f["properties"]["adm1_pcode"]
               for f in json.loads((REFERENCE / "gha_admin1.geojson").read_text())["features"]}
    districts = json.loads((REFERENCE / "gha_admin2.geojson").read_text())["features"]

    orphans = [d["properties"]["adm2_pcode"] for d in districts
               if d["properties"]["adm2_pcode"][:4] not in regions]
    if orphans:
        raise SystemExit(
            f"{len(orphans)} districts have a p-code with no matching region: "
            f"{', '.join(orphans[:5])}")

    area_regions = sum(f["properties"]["area_sqkm"]
                       for f in json.loads((REFERENCE / "gha_admin1.geojson").read_text())["features"])
    area_districts = sum(d["properties"]["area_sqkm"] for d in districts)
    if abs(area_regions - area_districts) > 1:
        raise SystemExit(
            f"Region and district areas disagree: {area_regions:,.0f} km2 vs "
            f"{area_districts:,.0f} km2. The two levels do not cover the same "
            f"territory.")

    log.info("hierarchy consistent: %d regions, %d districts, %s km2 at both levels",
             len(regions), len(districts), f"{area_regions:,.0f}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shapefiles", type=Path,
                        help="directory holding an original COD shapefile bundle")
    parser.add_argument("--verify", action="store_true",
                        help="check the reference boundaries and stop")
    args = parser.parse_args()

    step("01", "Administrative boundaries (Ghana COD-AB)")

    src = source("cod_ab_ghana")
    log.info("source: %s", src["name"])
    log.info("licence: %s", src["licence"])
    log.info("vintage: %s, version %s", src["vintage"], src["version"])

    if args.shapefiles:
        sys.path.insert(0, str(ROOT / "pipelines"))
        convert_bundle(args.shapefiles)

    verify()

    if args.verify:
        log.info("Reference boundaries verified.")
        return

    log.info("Step 01 complete. Boundaries are in %s", REFERENCE)
    log.info("Next: 20_load_postgis.py loads them into core.admin_*")


if __name__ == "__main__":
    main()
