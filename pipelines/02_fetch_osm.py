"""Step 02 - OpenStreetMap, from the Geofabrik Ghana extract.

The whole country is one 60-odd MB PBF file, so there is no reason to hit the
Overpass API layer by layer. Download once, read layers out of it locally,
re-run as often as you like.

Licence note: OSM is ODbL, which is share-alike. Anything derived from these
layers and published carries the same obligation. Keep OSM-derived tables
tagged with source_id = 'osm_ghana' so the exporter can honour that
automatically.

Usage:
    python pipelines/02_fetch_osm.py                 # all layers
    python pipelines/02_fetch_osm.py --layer roads
"""

from __future__ import annotations

import argparse

from common import GH, RAW, log, source, step
from common.validate import check_gdf

LAYERS = ["roads", "buildings", "waterways", "landuse", "places", "pois"]


def download_pbf():
    import requests

    src = source("osm_ghana")
    dest = RAW / "ghana-latest.osm.pbf"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        log.info("PBF already present: %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
        return dest

    log.info("downloading %s", src["url"])
    with requests.get(src["url"], stream=True, timeout=1800) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as fh:
            for block in r.iter_content(chunk_size=1 << 20):
                fh.write(block)
        tmp.rename(dest)
    log.info("saved %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


def extract(pbf, layer: str):
    """Pull one layer out of the PBF with pyrosm.

    pyrosm reads the protobuf directly and is far faster than round-tripping
    through ogr2ogr for a country-sized file.
    """
    from pyrosm import OSM

    osm = OSM(str(pbf))

    if layer == "roads":
        gdf = osm.get_network(network_type="all")
        # OSM's highway tag is the class everyone filters on downstream.
        if "highway" in gdf.columns:
            gdf = gdf.rename(columns={"highway": "class"})
        keep = [c for c in ("id", "name", "class", "surface", "oneway", "lanes", "geometry")
                if c in gdf.columns]
        gdf = gdf[keep]
        check_gdf(gdf, "osm roads", min_rows=50_000,
                  geom_types={"LineString", "MultiLineString"})

    elif layer == "buildings":
        gdf = osm.get_buildings()
        keep = [c for c in ("id", "name", "building", "height", "building:levels", "geometry")
                if c in gdf.columns]
        gdf = gdf[keep].rename(columns={"building": "class",
                                        "building:levels": "levels"})
        check_gdf(gdf, "osm buildings", min_rows=10_000,
                  geom_types={"Polygon", "MultiPolygon"})

    elif layer == "waterways":
        gdf = osm.get_data_by_custom_criteria(
            custom_filter={"waterway": ["river", "stream", "canal", "drain", "ditch"]},
            filter_type="keep", keep_nodes=False, keep_relations=False,
        )
        gdf = gdf.rename(columns={"waterway": "class"})
        check_gdf(gdf, "osm waterways", min_rows=1_000)

    elif layer == "landuse":
        gdf = osm.get_landuse()
        check_gdf(gdf, "osm landuse", min_rows=500)

    elif layer == "places":
        gdf = osm.get_data_by_custom_criteria(
            custom_filter={"place": True}, filter_type="keep",
            keep_ways=False, keep_relations=False,
        )
        check_gdf(gdf, "osm places", min_rows=1_000, geom_types={"Point"})

    elif layer == "pois":
        gdf = osm.get_pois(
            custom_filter={"amenity": ["hospital", "clinic", "doctors", "pharmacy",
                                       "school", "college", "university",
                                       "marketplace", "police", "fire_station"]}
        )
        check_gdf(gdf, "osm pois", min_rows=500)

    else:
        raise ValueError(f"unknown layer {layer}")

    return gdf.to_crs(4326)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", choices=LAYERS, help="one layer only")
    args = parser.parse_args()

    step("02", "OpenStreetMap extract")
    pbf = download_pbf()

    for layer in ([args.layer] if args.layer else LAYERS):
        log.info("extracting %s", layer)
        try:
            gdf = extract(pbf, layer)
        except Exception as exc:
            # One missing tag combination should not kill the whole run.
            log.error("%s failed: %s", layer, exc)
            continue

        out = RAW / f"osm_{layer}.parquet"
        gdf.to_parquet(out, compression="zstd")
        log.info("%s: %s features -> %s", layer, f"{len(gdf):,}", out.name)

    log.info("Step 02 complete.")


if __name__ == "__main__":
    main()
