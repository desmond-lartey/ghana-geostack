"""Assemble the static site served by Vercel.

Produces a self-contained `public/` directory: the viewer, the committed
boundaries, and any GeoParquet exports that exist at build time. Uses the
standard library only, so the Vercel build image needs nothing installed.

Configuration comes from the environment, which is how it is set in the Vercel
project settings:

    TILES_URL     public pg_tileserv endpoint. Leave unset for a
                  boundaries-only deployment, which is the safe default —
                  the viewer detects the absence and disables the layers that
                  need a database rather than failing.
    SITE_URL      canonical URL, used in the sitemap.
    INCLUDE_EXPORTS  set to 0 to skip GeoParquet even when present.

Usage:
    python scripts/build_web.py
    TILES_URL=https://tiles.example.org python scripts/build_web.py
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public"

TILES_URL = os.getenv("TILES_URL", "").strip()
SITE_URL = os.getenv("SITE_URL", "").strip().rstrip("/")
INCLUDE_EXPORTS = os.getenv("INCLUDE_EXPORTS", "1") != "0"

# Exports above this size are skipped. Vercel's static hosting is not the right
# place for a multi-gigabyte building table; publish those as release
# artefacts or from object storage instead.
MAX_EXPORT_MB = 40


def log(message: str) -> None:
    print(f"  {message}", flush=True)


def clean() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)


def compiled_catalog() -> str:
    """config/catalog.yml as compact JSON for the viewer.

    The viewer holds a compiled copy so it never parses YAML in the browser.
    Recompiling at build time is what stops the two drifting apart.
    """
    import json

    try:
        import yaml
    except ImportError:
        return ""   # not installed on the build image; keep whatever is in the file

    with open(ROOT / "config" / "catalog.yml", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    compact = []
    for dataset in doc["datasets"]:
        entry = {k: dataset[k] for k in
                 ("id", "title", "theme", "licence", "attribution",
                  "resolution", "cadence", "notes")}
        entry["notes"] = " ".join(entry["notes"].split())
        if "browser" in dataset:
            entry["browser"] = dataset["browser"]
        if "gee" in dataset:
            entry["gee"] = {"collection": dataset["gee"]["collection"]}
        compact.append(entry)

    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))


def copy_viewer() -> None:
    source = ROOT / "web" / "index.html"
    if not source.exists():
        sys.exit("web/index.html is missing")

    html = source.read_text(encoding="utf-8")

    catalog = compiled_catalog()
    if catalog:
        html = re.sub(r"const CATALOG = \[.*?\];\n",
                      f"const CATALOG = {catalog};\n", html, count=1, flags=re.S)
        log(f"catalogue recompiled from config/catalog.yml ({len(catalog) / 1024:.0f} KB)")

    # In the built site the data sits beside the page rather than one level up.
    html = re.sub(r'(<meta name="gh:data-root" content=")[^"]*(">)',
                  r"\1./data\2", html)
    html = re.sub(r'(<meta name="gh:tiles-url" content=")[^"]*(">)',
                  rf'\1{TILES_URL}\2', html)

    (OUT / "index.html").write_text(html, encoding="utf-8")

    for icon in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        source_icon = ROOT / "web" / icon
        if source_icon.exists():
            shutil.copy2(source_icon, OUT / icon)
    log(f"index.html ({len(html) / 1024:.0f} KB)"
        + (f", tiles -> {TILES_URL}" if TILES_URL else ", boundaries only"))


def copy_data() -> None:
    reference = ROOT / "data" / "reference"
    target = OUT / "data" / "reference"
    target.mkdir(parents=True, exist_ok=True)

    files = sorted(reference.glob("*.geojson"))
    if not files:
        sys.exit("No boundaries in data/reference. Run pipelines/01_fetch_admin.py.")

    for path in files:
        shutil.copy2(path, target / path.name)
        log(f"{path.name} ({path.stat().st_size / 1e6:.1f} MB)")

    if not INCLUDE_EXPORTS:
        return

    exports = ROOT / "data" / "exports"
    if not exports.exists():
        return

    export_target = OUT / "data" / "exports"
    export_target.mkdir(parents=True, exist_ok=True)

    for path in sorted(exports.glob("*.parquet")):
        size_mb = path.stat().st_size / 1e6
        if size_mb > MAX_EXPORT_MB:
            log(f"skipped {path.name} ({size_mb:.0f} MB, over the {MAX_EXPORT_MB} MB limit)")
            continue
        shutil.copy2(path, export_target / path.name)
        log(f"{path.name} ({size_mb:.1f} MB)")

    for name in ("attribution.md", "manifest.json"):
        if (exports / name).exists():
            shutil.copy2(exports / name, export_target / name)


def write_metadata() -> None:
    """robots.txt and a sitemap, so the deployment is indexable."""
    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n"
        + (f"Sitemap: {SITE_URL}/sitemap.xml\n" if SITE_URL else ""),
        encoding="utf-8")

    if SITE_URL:
        (OUT / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{SITE_URL}/</loc>"
            f"<lastmod>{date.today().isoformat()}</lastmod></url>\n"
            "</urlset>\n",
            encoding="utf-8")


def report() -> None:
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    count = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"\nBuilt public/ — {count} files, {total / 1e6:.1f} MB")


def index_earth_engine() -> None:
    """Refresh the Earth Engine catalogue index, if the network allows.

    Deliberately advisory. The viewer searches this index when it is present
    and says so plainly when it is not, so a slow or unreachable Google must
    never take the deployment down with it.
    """
    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_ee_catalog.py")],
            capture_output=True, text=True, timeout=600)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log(f"Earth Engine index skipped ({type(exc).__name__})")
        return

    for line in result.stderr.strip().splitlines():
        log(line.strip())

    if result.returncode != 0:
        log("Earth Engine index skipped; the viewer falls back to the curated catalogue")


def main() -> None:
    print("Building the static site")
    clean()
    copy_viewer()
    copy_data()
    index_earth_engine()
    write_metadata()
    report()


if __name__ == "__main__":
    main()
