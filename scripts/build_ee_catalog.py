"""Index the Earth Engine data catalogue for in-browser search.

Earth Engine publishes its catalogue as a public STAC tree: a root catalogue
of provider catalogues, each holding collection documents. No account is
needed to read it. This walks that tree once at build time and writes a single
compact index the viewer can search offline.

Why build time rather than run time: the tree is roughly 1,100 separate
documents. Crawling it from a browser on every page load would be absurd, and
bundling a stale copy in the repository means it drifts. Vercel rebuilds on
every push, so the index is refreshed whenever the site is.

    python scripts/build_ee_catalog.py            # writes public/data/ee-catalog.json
    python scripts/build_ee_catalog.py --limit 40 # a quick sample while developing

The build must never fail because Google was slow. If the crawl cannot
complete, this writes nothing and returns cleanly; the viewer then falls back
to the curated catalogue in config/catalog.yml and says why.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data" / "ee-catalog.json"

STAC_ROOT = "https://storage.googleapis.com/earthengine-stac/catalog/catalog.json"

# Ghana's bounding box, with a small margin. Used only to flag which datasets
# actually cover the country — nothing is excluded on this basis, because a
# global dataset is still the right answer to most questions.
GHANA_BBOX = (-3.35, 4.65, 1.30, 11.25)

TIMEOUT = 30
WORKERS = 16

# A description trimmed to roughly a paragraph. The full text is a page of
# HTML for some datasets, and the viewer links to the real catalogue page.
DESCRIPTION_CHARS = 420


def fetch_json(url: str) -> dict | None:
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "ghana-geostack/1.0 (catalogue indexer)"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def child_links(document: dict) -> list[str]:
    return [link["href"] for link in document.get("links", [])
            if link.get("rel") == "child" and link.get("href")]


def collect_collection_urls(limit: int | None) -> list[str]:
    """Walk the catalogue tree and return every collection document URL.

    A node is a catalogue if it has children, and a collection if it does not.
    The tree is shallow — provider, then sometimes one more level — so this
    stays a breadth-first walk rather than anything cleverer.
    """
    root = fetch_json(STAC_ROOT)
    if not root:
        return []

    pending = child_links(root)
    collections: list[str] = []
    seen: set[str] = set()

    while pending:
        batch, pending = pending, []

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(fetch_json, url): url for url in batch
                       if url not in seen}
            for future in as_completed(futures):
                url = futures[future]
                seen.add(url)
                document = future.result()
                if not document:
                    continue

                children = child_links(document)
                if children:
                    pending.extend(c for c in children if c not in seen)
                elif document.get("type") == "Collection" or document.get("gee:type"):
                    collections.append(url)
                    # The document is already in hand, so it is cached rather
                    # than fetched a second time in the next pass.
                    CACHE[url] = document

        print(f"  {len(collections)} collections found, {len(pending)} catalogues to walk",
              file=sys.stderr)

        if limit and len(collections) >= limit:
            return collections[:limit]

    return collections


CACHE: dict[str, dict] = {}


def intersects_ghana(bbox: list[float]) -> bool:
    west, south, east, north = bbox[0], bbox[1], bbox[2], bbox[3]
    gw, gs, ge, gn = GHANA_BBOX
    return not (east < gw or west > ge or north < gs or south > gn)


def default_visualisation(document: dict) -> dict | None:
    """The producer's own suggested rendering, if they gave one.

    This is what makes a dataset usable the moment it is added: Earth Engine
    ships a band selection, a range and a palette for most collections, so the
    layer arrives styled rather than as a grey rectangle the user has to guess
    a stretch for.
    """
    for entry in document.get("gee:visualizations", []):
        band_vis = (entry.get("image_visualization") or {}).get("band_vis")
        if not band_vis:
            continue

        vis: dict = {}
        if band_vis.get("bands"):
            vis["bands"] = band_vis["bands"]
        # Earth Engine writes min and max as single-element lists when the
        # same value applies to every band.
        for key in ("min", "max"):
            value = band_vis.get(key)
            if isinstance(value, list) and value:
                vis[key] = value[0] if len(value) == 1 else value
            elif isinstance(value, (int, float)):
                vis[key] = value
        if band_vis.get("palette"):
            vis["palette"] = band_vis["palette"]
        if band_vis.get("gamma"):
            gamma = band_vis["gamma"]
            vis["gamma"] = gamma[0] if isinstance(gamma, list) and gamma else gamma

        if vis:
            vis["label"] = entry.get("display_name") or "Default"
            return vis
    return None


def summarise(document: dict) -> dict | None:
    """One catalogue entry, reduced to what a search needs."""
    dataset_id = document.get("id")
    gee_type = document.get("gee:type")
    if not dataset_id or not gee_type:
        return None

    # Deprecated datasets still resolve but should not be recommended.
    if document.get("gee:status") == "deprecated":
        return None

    summaries = document.get("summaries") or {}
    bands = [
        {"name": b.get("name"), "description": (b.get("description") or "")[:120]}
        for b in (summaries.get("eo:bands") or [])
        if b.get("name")
    ]

    gsd = summaries.get("gsd") or []
    if isinstance(gsd, dict):          # some entries give a min/max object
        gsd = [gsd.get("minimum")]
    resolution = next((g for g in gsd if isinstance(g, (int, float))), None)

    extent = document.get("extent") or {}
    interval = ((extent.get("temporal") or {}).get("interval") or [[None, None]])[0]
    bboxes = (extent.get("spatial") or {}).get("bbox") or [[-180, -90, 180, 90]]

    providers = document.get("providers") or []
    licensor = next(
        (p.get("name") for p in providers if "licensor" in (p.get("roles") or [])),
        next((p.get("name") for p in providers if "producer" in (p.get("roles") or [])), None))

    description = " ".join((document.get("description") or "").split())
    if len(description) > DESCRIPTION_CHARS:
        description = description[:DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "…"

    entry = {
        "id": dataset_id,
        "title": document.get("title") or dataset_id,
        "type": gee_type,                       # image | image_collection | table
        "description": description,
        "licence": document.get("license"),
        "provider": licensor,
        "keywords": document.get("keywords") or [],
        "start": (interval[0] or "")[:10] or None,
        "end": (interval[1] or "")[:10] or None,
        "resolution_m": resolution,
        "bands": bands[:24],
        "covers_ghana": any(intersects_ghana(b) for b in bboxes if len(b) >= 4),
        "url": "https://developers.google.com/earth-engine/datasets/catalog/"
               + dataset_id.replace("/", "_"),
    }

    vis = default_visualisation(document)
    if vis:
        entry["vis"] = vis

    return {k: v for k, v in entry.items() if v not in (None, [], "")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int,
                        help="stop after this many collections, for a quick test")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    print("Indexing the Earth Engine catalogue", file=sys.stderr)

    urls = collect_collection_urls(args.limit)
    if not urls:
        # Not an error. The site is expected to build without this.
        print("  catalogue unreachable — skipping, the viewer will say so",
              file=sys.stderr)
        return

    entries = []
    missing = [u for u in urls if u not in CACHE]

    if missing:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(fetch_json, url): url for url in missing}
            for future in as_completed(futures):
                document = future.result()
                if document:
                    CACHE[futures[future]] = document

    for url in urls:
        document = CACHE.get(url)
        if not document:
            continue
        entry = summarise(document)
        if entry:
            entries.append(entry)

    if not entries:
        print("  nothing usable in the catalogue — skipping", file=sys.stderr)
        return

    entries.sort(key=lambda e: (not e.get("covers_ghana"), e["title"].lower()))

    payload = {
        "source": STAC_ROOT,
        "count": len(entries),
        "ghana": sum(1 for e in entries if e.get("covers_ghana")),
        "datasets": entries,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")))

    size_kb = args.out.stat().st_size / 1024
    print(f"  {len(entries)} datasets, {payload['ghana']} covering Ghana "
          f"→ {args.out.relative_to(ROOT)} ({size_kb:.0f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
