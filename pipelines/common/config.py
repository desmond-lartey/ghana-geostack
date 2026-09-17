"""Load config/ghana.yml and config/sources.yml once, expose them as objects.

The original Denver pipeline hardcoded a Windows path and a bbox in every
script. Anything that is a constant about Ghana lives in config/ghana.yml and
is read from here instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Repo root, resolved from this file rather than the working directory, so the
# pipelines run the same from the repo root, from a notebook, or from cron.
ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.getenv("GHANA_DATA_DIR", ROOT / "data"))

RAW = DATA_DIR / "raw"
INTERIM = DATA_DIR / "interim"
PROCESSED = DATA_DIR / "processed"
EXPORTS = DATA_DIR / "exports"

for _d in (RAW, INTERIM, PROCESSED, EXPORTS):
    _d.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)

    def as_wkt(self) -> str:
        w, s, e, n = self.as_tuple()
        return (
            f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))"
        )

    def as_overpass(self) -> str:
        """Overpass and osmnx want south,west,north,east. Getting this order
        wrong is the single most common bug in OSM download code."""
        return f"{self.south},{self.west},{self.north},{self.east}"


@dataclass(frozen=True)
class Ghana:
    bbox: BBox
    storage_srid: int
    metric_srid: int
    regions: list[str]
    expected_regions: int
    expected_districts: int
    center: dict[str, float]
    h3: dict[str, int]
    cities: dict[str, dict[str, float]]
    raw: dict[str, Any]

    def city_bbox(self, name: str) -> BBox:
        """Approximate bbox around a city, for local-scale test runs.

        Uses a flat-earth degree conversion, which is accurate enough for a
        download envelope at Ghana's latitudes and avoids a pyproj dependency
        in the config layer.
        """
        import math

        c = self.cities[name]
        km = c["radius_km"]
        dlat = km / 110.574
        dlon = km / (111.320 * math.cos(math.radians(c["lat"])))
        return BBox(
            west=round(c["lon"] - dlon, 5),
            south=round(c["lat"] - dlat, 5),
            east=round(c["lon"] + dlon, 5),
            north=round(c["lat"] + dlat, 5),
        )


@lru_cache(maxsize=1)
def load_ghana() -> Ghana:
    with open(CONFIG_DIR / "ghana.yml", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    b = raw["bbox"]
    return Ghana(
        bbox=BBox(b["west"], b["south"], b["east"], b["north"]),
        storage_srid=raw["crs"]["storage"],
        metric_srid=raw["crs"]["metric"],
        regions=raw["regions"],
        expected_regions=raw["admin"]["expected_regions"],
        expected_districts=raw["admin"]["expected_districts"],
        center=raw["center"],
        h3=raw["h3"],
        cities=raw["cities"],
        raw=raw,
    )


@lru_cache(maxsize=1)
def load_sources() -> dict[str, dict[str, Any]]:
    """Return the data catalogue keyed by source id."""
    with open(CONFIG_DIR / "sources.yml", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return {s["id"]: s for s in doc["sources"]}


def source(source_id: str) -> dict[str, Any]:
    """Fetch one catalogue entry, failing loudly if it is not registered.

    This is deliberately strict. If a pipeline wants to download something
    that is not in sources.yml, the licence and attribution have not been
    thought about yet, and that is exactly the failure we want to prevent.
    """
    sources = load_sources()
    if source_id not in sources:
        raise KeyError(
            f"'{source_id}' is not in config/sources.yml. Add a catalogue "
            f"entry with its licence and attribution before fetching it."
        )
    return sources[source_id]


GH = load_ghana()
