"""Validation helpers.

The habit worth copying from the GeoSQL skill: nothing is presented until it
has been checked, and the check is a query, not a glance at a map. These
helpers make the check one line so there is no excuse to skip it.

Every function raises ValidationError on failure. A pipeline step that calls
them cannot quietly produce a wrong table.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import GH
from .log import log


class ValidationError(AssertionError):
    """Raised when a dataset fails a check. Never caught inside a pipeline."""


@dataclass
class Check:
    name: str
    passed: bool
    observed: object
    expected: str

    def __str__(self) -> str:
        mark = "ok  " if self.passed else "FAIL"
        return f"  [{mark}] {self.name}: {self.observed}  (expected {self.expected})"


def report(checks: list[Check], context: str) -> None:
    """Print all checks, then raise if any failed.

    All of them print first. Debugging is much easier when you can see every
    check at once rather than the first one that blew up.
    """
    log.info("Validation — %s", context)
    for c in checks:
        log.info("%s", c)
    failed = [c for c in checks if not c.passed]
    if failed:
        raise ValidationError(
            f"{len(failed)} of {len(checks)} checks failed for {context}: "
            + ", ".join(c.name for c in failed)
        )


# ── GeoDataFrame checks, used at the fetch and build stages ────────────────

def check_gdf(gdf, name: str, *, min_rows: int = 1,
              expect_srid: int = 4326, geom_types: set[str] | None = None,
              max_rows: int | None = None) -> None:
    """Validate a GeoDataFrame before it is written or loaded.

    Catches the four failures that account for almost every bad map: no rows,
    wrong CRS, invalid geometry, and features outside Ghana.
    """
    checks: list[Check] = []

    n = len(gdf)
    checks.append(Check("row_count", n >= min_rows, n, f">= {min_rows}"))
    if max_rows is not None:
        checks.append(Check("row_count_ceiling", n <= max_rows, n, f"<= {max_rows}"))

    epsg = gdf.crs.to_epsg() if gdf.crs else None
    checks.append(Check("crs", epsg == expect_srid, epsg, f"EPSG:{expect_srid}"))

    if n:
        invalid = int((~gdf.geometry.is_valid).sum())
        checks.append(Check("valid_geometry", invalid == 0, invalid, "0"))

        empty = int(gdf.geometry.is_empty.sum() + gdf.geometry.isna().sum())
        checks.append(Check("non_empty_geometry", empty == 0, empty, "0"))

        if geom_types:
            found = set(gdf.geometry.geom_type.unique())
            checks.append(
                Check("geometry_type", found <= geom_types, sorted(found),
                      " or ".join(sorted(geom_types)))
            )

        # Everything must land inside Ghana. This one check catches lon/lat
        # swaps, null island, and an assumed source CRS all at once.
        if epsg == 4326:
            w, s, e, nn = GH.bbox.as_tuple()
            bounds = gdf.total_bounds  # minx, miny, maxx, maxy
            inside = (
                bounds[0] >= w - 0.5 and bounds[1] >= s - 0.5
                and bounds[2] <= e + 0.5 and bounds[3] <= nn + 0.5
            )
            checks.append(
                Check("within_ghana", inside,
                      [round(float(b), 3) for b in bounds],
                      f"within {GH.bbox.as_tuple()}")
            )

    report(checks, name)


# ── Database checks, used after loading ────────────────────────────────────

def check_table(schema: str, table: str, *, min_rows: int = 1,
                expect_srid: int = 4326) -> None:
    """Validate a table that has already landed in PostGIS."""
    from . import db

    checks: list[Check] = []

    n = db.scalar(f"SELECT count(*) FROM {schema}.{table}")
    checks.append(Check("row_count", n >= min_rows, n, f">= {min_rows}"))

    srid = db.scalar(
        "SELECT srid FROM geometry_columns "
        "WHERE f_table_schema = %s AND f_table_name = %s LIMIT 1",
        (schema, table),
    )
    if srid is not None:
        checks.append(Check("srid", srid == expect_srid, srid, str(expect_srid)))

        invalid = db.scalar(
            f"SELECT count(*) FROM {schema}.{table} WHERE NOT ST_IsValid(geom)")
        checks.append(Check("valid_geometry", invalid == 0, invalid, "0"))

        outside = db.scalar(
            f"SELECT count(*) FROM {schema}.{table} "
            f"WHERE geom IS NOT NULL AND NOT (geom && core.gh_bbox())")
        checks.append(Check("within_ghana", outside == 0, outside, "0"))

    report(checks, f"{schema}.{table}")


def check_magnitude(schema: str, table: str, *, kind: str,
                    low: float, high: float, unit: str = "km2") -> None:
    """Check total area or length against a plausible range.

    This is the check that catches the errors row counts cannot see: the right
    number of features with the wrong geometry. A roads table with the correct
    row count but a total length of 40 km is broken, and only this test says so.
    """
    from . import db

    if kind == "area":
        expr = "sum(ST_Area(ST_Transform(geom, 32630))) / 1e6"
    elif kind == "length":
        expr = "sum(ST_Length(ST_Transform(geom, 32630))) / 1000"
    else:
        raise ValueError("kind must be 'area' or 'length'")

    value = db.scalar(f"SELECT {expr} FROM {schema}.{table}") or 0
    report(
        [Check(f"total_{kind}_{unit}", low <= value <= high,
               round(float(value), 1), f"{low:,}–{high:,} {unit}")],
        f"{schema}.{table} magnitude",
    )


# Reference magnitudes for Ghana, used as expectations across the pipeline.
# Sourced from published national figures; treat as order-of-magnitude guards
# rather than precise truth.
GHANA_EXPECTATIONS = {
    "land_area_km2": (230_000, 245_000),      # ~238,533
    "coastline_km": (500, 600),               # ~539
    "road_network_km": (60_000, 200_000),     # OSM coverage varies with extract date
    "building_count": (3_000_000, 20_000_000),  # OSM alone is far lower than ML sources
    "population": (30_000_000, 36_000_000),   # 2021 PHC counted ~30.8 million
}
