"""Step 04 — Earth Engine, driven by the catalogue.

Exports a Ghana-clipped raster for any dataset in `config/catalog.yml` that
carries a `gee` block. The collection id, bands, reducer and scale all come
from the catalogue, so this file never grows a list of its own.

Earth Engine needs a Google Cloud project with the API enabled, and a one-off
authentication. Both are stored, so it is done once:

    earthengine authenticate
    echo "GEE_PROJECT=your-project-id" >> .env

Usage:
    python pipelines/04_fetch_gee.py --list
    python pipelines/04_fetch_gee.py --show esa_worldcover
    python pipelines/04_fetch_gee.py esa_worldcover
    python pipelines/04_fetch_gee.py chirps_rainfall --start 2024-01-01 --end 2024-12-31
    python pipelines/04_fetch_gee.py sentinel2_l2a --start 2024-11-01 --end 2025-02-28 --city accra

Small areas download directly. Anything national at 10 m is too large for a
direct download, so the export goes to Drive and the step says so rather than
failing on a size limit twenty minutes in.
"""

from __future__ import annotations

import argparse
import os

import yaml
from common import GH, RAW, ROOT, log, step

CATALOG = ROOT / "config" / "catalog.yml"

# Earth Engine refuses a direct download above roughly 50 MB. This is the
# pixel count that tends to sit under it for a single-band export; past it the
# step routes to Drive instead of discovering the limit the hard way.
DIRECT_DOWNLOAD_PIXEL_LIMIT = 20_000_000

REDUCERS = {
    "median": "median",
    "mean": "mean",
    "max": "max",
    "min": "min",
    "sum": "sum",
    "mode": "mode",
    "mosaic": "mosaic",
}


def load_catalog() -> dict[str, dict]:
    with open(CATALOG, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return {d["id"]: d for d in doc["datasets"]}


def show_catalog(catalog: dict[str, dict]) -> None:
    by_theme: dict[str, list] = {}
    for entry in catalog.values():
        by_theme.setdefault(entry["theme"], []).append(entry)

    for theme in sorted(by_theme):
        print(f"\n{theme.upper()}")
        for entry in sorted(by_theme[theme], key=lambda e: e["id"]):
            routes = []
            if "browser" in entry:
                routes.append("viewer")
            if "gee" in entry:
                routes.append("pipeline")
            print(f"  {entry['id']:24} {entry['title']:38} "
                  f"{entry['resolution']:>8}  [{', '.join(routes)}]")

    print("\nRun with an id to fetch it. --show <id> prints the full entry.")


def show_entry(entry: dict) -> None:
    print(f"\n{entry['title']}")
    print(f"  id          {entry['id']}")
    print(f"  theme       {entry['theme']}")
    print(f"  resolution  {entry['resolution']}")
    print(f"  cadence     {entry['cadence']}")
    print(f"  licence     {entry['licence']}")
    print(f"  credit      {entry['attribution']}")
    if "gee" in entry:
        gee = entry["gee"]
        print(f"  collection  {gee['collection']}")
        print(f"  bands       {', '.join(gee['bands'])}")
        print(f"  reducer     {gee['reducer']} at {gee['scale']} m")
    if "browser" in entry:
        print("  viewer      loads directly, no account needed")
    print(f"\n  {entry['notes'].strip()}\n")


def initialise(project: str | None):
    """Start Earth Engine, with the failures explained rather than raised raw."""
    try:
        import ee
    except ImportError:
        raise SystemExit(
            "earthengine-api is not installed.\n"
            "  pip install earthengine-api\n"
            "or use the browser layers, which need no account at all."
        ) from None

    project = project or os.getenv("GEE_PROJECT")
    if not project:
        raise SystemExit(
            "No Earth Engine project. Either pass --project, or add it once:\n"
            "  echo 'GEE_PROJECT=your-project-id' >> .env\n\n"
            "The project must have the Earth Engine API enabled at\n"
            "  https://console.cloud.google.com/apis/library/earthengine.googleapis.com"
        )

    try:
        ee.Initialize(project=project)
    except Exception:
        raise SystemExit(
            f"Could not initialise Earth Engine for project '{project}'.\n"
            "Authenticate once with:\n"
            "  earthengine authenticate\n"
            "then check the project id and that the API is enabled."
        ) from None

    log.info("Earth Engine ready, project %s", project)
    return ee


def ghana_geometry(ee, city: str | None):
    """The export footprint: the whole country, or one city's envelope."""
    if city:
        bbox = GH.city_bbox(city)
        log.info("clipping to %s", city)
    else:
        bbox = GH.bbox
    w, s, e, n = bbox.as_tuple()
    return ee.Geometry.Rectangle([w, s, e, n], "EPSG:4326", geodesic=False)


def is_vector(entry: dict) -> bool:
    """A catalogue entry with no bands and no scale is a FeatureCollection."""
    gee = entry["gee"]
    return not gee.get("bands") and not gee.get("scale")


def fetch_vector(ee, entry: dict, region, scope: str) -> None:
    """Export a FeatureCollection clipped to Ghana, as GeoJSON.

    Boundaries, catchments and urban extents are vectors, and forcing them
    through a raster export would throw away exactly the attributes that make
    them useful — HYBAS_ID and NEXT_DOWN carry the river topology.
    """
    collection = ee.FeatureCollection(entry["gee"]["collection"]).filterBounds(region)

    # geoBoundaries CGAZ is global and carries a country code, so filter on it
    # rather than relying on the spatial intersection alone.
    if "geoboundaries" in entry["gee"]["collection"].lower():
        collection = collection.filter(ee.Filter.eq("shapeGroup", "GHA"))

    count = collection.size().getInfo()
    log.info("%d features intersect Ghana", count)
    if count == 0:
        raise SystemExit("Nothing intersects Ghana. Check the collection id.")

    name = f"{entry['id']}_{scope}"

    # Direct download works for a few hundred features; past that the payload
    # exceeds what getDownloadURL will serve, so Drive takes over.
    if count > 3000:
        log.info("%d features is past the direct-download limit — exporting to Drive", count)
        task = ee.batch.Export.table.toDrive(
            collection=collection,
            description=name,
            folder="ghana-geostack",
            fileNamePrefix=name,
            fileFormat="GeoJSON",
        )
        task.start()
        log.info("export started: %s", name)
        log.info("Watch it at https://code.earthengine.google.com/tasks")
        return

    import requests

    url = collection.getDownloadURL(filetype="GeoJSON", filename=name)
    destination = RAW / f"{name}.geojson"
    log.info("downloading to %s", destination.name)

    with requests.get(url, stream=True, timeout=1800) as response:
        response.raise_for_status()
        with open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 20):
                fh.write(chunk)

    log.info("saved %s (%.1f MB)", destination.name, destination.stat().st_size / 1e6)
    log.info("Summarise a raster onto it with:")
    log.info("  python pipelines/05_zonal_stats.py <raster> --zones %s", destination)


def build_image(ee, entry: dict, region, start: str | None, end: str | None):
    """Reduce a collection to one image, or take an image as it is."""
    gee = entry["gee"]
    collection_id = gee["collection"]
    bands = gee["bands"]
    reducer = gee["reducer"]

    # An id can name either a collection or a single image; try the collection
    # first, because that is the common case.
    try:
        collection = ee.ImageCollection(collection_id).filterBounds(region)
        if start and end:
            collection = collection.filterDate(start, end)
            log.info("filtered to %s .. %s", start, end)

        count = collection.size().getInfo()
        if count == 0:
            raise SystemExit(
                "No images matched. Widen the date range, or check that the "
                "collection covers Ghana for that period."
            )
        log.info("%d images in the collection", count)

        # Cloud masking for the optical collections, where it is the difference
        # between a usable composite and a picture of cloud.
        if "S2" in collection_id:
            collection = collection.map(mask_sentinel2(ee))
        elif "LANDSAT" in collection_id:
            collection = collection.map(mask_landsat(ee))

        image = getattr(collection.select(bands), REDUCERS[reducer])()

        # QA_PIXEL has done its job once the mask is applied, and carrying it
        # into the export doubles the file for no benefit.
        if "QA_PIXEL" in bands:
            image = image.select([b for b in bands if b != "QA_PIXEL"])
            log.info("thermal band exported as raw DN — convert with "
                     "--scale 0.00341802 --offset -124.15 for Celsius")
    except SystemExit:
        raise
    except Exception:
        log.info("not a collection, treating %s as a single image", collection_id)
        image = ee.Image(collection_id).select(bands)

    return image.clip(region)


def mask_sentinel2(ee):
    def apply(image):
        scl = image.select("SCL")
        # 3 cloud shadow, 8 medium-probability cloud, 9 high, 10 cirrus
        keep = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return image.updateMask(keep)
    return apply


def mask_landsat(ee):
    """Drop cloud, cloud shadow, dilated cloud and cirrus.

    Collection 2 QA_PIXEL bits: 1 dilated cloud, 2 cirrus, 3 cloud,
    4 cloud shadow. A thermal composite built over cloud reads the cloud top,
    not the ground, which is tens of degrees out.
    """
    def apply(image):
        qa = image.select("QA_PIXEL")
        clear = (qa.bitwiseAnd(1 << 1).eq(0)
                 .And(qa.bitwiseAnd(1 << 2).eq(0))
                 .And(qa.bitwiseAnd(1 << 3).eq(0))
                 .And(qa.bitwiseAnd(1 << 4).eq(0)))
        return image.updateMask(clear)
    return apply


def estimate_pixels(entry: dict, city: str | None) -> int:
    bbox = GH.city_bbox(city) if city else GH.bbox
    w, s, e, n = bbox.as_tuple()
    width_m = (e - w) * 111_320 * 0.99
    height_m = (n - s) * 110_570
    scale = entry["gee"]["scale"]
    return int((width_m / scale) * (height_m / scale) * len(entry["gee"]["bands"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", nargs="?", help="catalogue id to fetch")
    parser.add_argument("--list", action="store_true", help="list the catalogue")
    parser.add_argument("--show", metavar="ID", help="print one catalogue entry")
    parser.add_argument("--project", help="Earth Engine project id; defaults to GEE_PROJECT")
    parser.add_argument("--start", help="start date, YYYY-MM-DD")
    parser.add_argument("--end", help="end date, YYYY-MM-DD")
    parser.add_argument("--city", choices=sorted(GH.cities),
                        help="clip to one city instead of the country")
    parser.add_argument("--scale", type=int, help="override the catalogue resolution")
    parser.add_argument("--drive", action="store_true",
                        help="export to Drive even when a direct download would fit")
    args = parser.parse_args()

    catalog = load_catalog()

    if args.list or not (args.dataset or args.show):
        show_catalog(catalog)
        return

    if args.show:
        if args.show not in catalog:
            raise SystemExit(f"'{args.show}' is not in the catalogue. Try --list.")
        show_entry(catalog[args.show])
        return

    if args.dataset not in catalog:
        raise SystemExit(f"'{args.dataset}' is not in the catalogue. Try --list.")

    entry = catalog[args.dataset]
    if "gee" not in entry:
        route = "the viewer's Data tab" if "browser" in entry else "another source"
        raise SystemExit(
            f"'{args.dataset}' has no Earth Engine entry. Use {route} instead."
        )

    step("04", f"Earth Engine — {entry['title']}")
    log.info("licence: %s", entry["licence"])
    log.info("credit: %s", entry["attribution"])

    ee = initialise(args.project)
    region = ghana_geometry(ee, args.city)
    scope = args.city or "ghana"

    if is_vector(entry):
        fetch_vector(ee, entry, region, scope)
        log.info("Step 04 complete.")
        return

    image = build_image(ee, entry, region, args.start, args.end)

    scale = args.scale or entry["gee"]["scale"]
    pixels = estimate_pixels(entry, args.city)
    log.info("about %s pixels at %d m", f"{pixels:,}", scale)

    name = f"{entry['id']}_{scope}"

    if args.drive or pixels > DIRECT_DOWNLOAD_PIXEL_LIMIT:
        log.info("too large for a direct download — exporting to Drive")
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=name,
            folder="ghana-geostack",
            fileNamePrefix=name,
            region=region,
            scale=scale,
            crs="EPSG:4326",
            maxPixels=1e10,
            fileFormat="GeoTIFF",
            formatOptions={"cloudOptimized": True},
        )
        task.start()
        log.info("export started: %s", name)
        log.info("Watch it at https://code.earthengine.google.com/tasks")
        log.info("When it finishes, put the file in %s and load it with", RAW)
        log.info("  python pipelines/20_load_postgis.py --only terrain")
        return

    url = image.getDownloadURL({
        "region": region,
        "scale": scale,
        "crs": "EPSG:4326",
        "format": "GEO_TIFF",
    })

    import requests

    destination = RAW / f"{name}.tif"
    log.info("downloading to %s", destination.name)
    with requests.get(url, stream=True, timeout=1800) as response:
        response.raise_for_status()
        with open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 20):
                fh.write(chunk)

    size_mb = destination.stat().st_size / 1e6
    log.info("saved %s (%.1f MB)", destination.name, size_mb)

    if size_mb < 0.01:
        raise SystemExit(
            "The file is empty. Usually the date range matched no images, or "
            "the bands are not present in that collection."
        )

    log.info("Step 04 complete. Register it in config/sources.yml, then load it.")


if __name__ == "__main__":
    main()
