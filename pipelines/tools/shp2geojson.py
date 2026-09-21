"""Convert ESRI Shapefiles to GeoJSON without GDAL, GeoPandas or pyshp.

Administrative boundaries are usually distributed as shapefiles, and the
GDAL stack is the hardest part of a geospatial install to get working. This
module reads the .shp, .dbf and .prj directly, so boundaries can be ingested
on any machine with a Python interpreter.

For every other conversion in this project, use GeoPandas. This exists for the
one case where boundaries must load before the environment is complete.

Usage:
    python pipelines/tools/shp2geojson.py data/raw/gha_admin1.shp
    python pipelines/tools/shp2geojson.py data/raw/*.shp --outdir data/reference
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

# Shapefile shape type codes that this reader handles.
POINT_TYPES = {1, 11, 21}
POLYLINE_TYPES = {3, 13, 23}
POLYGON_TYPES = {5, 15, 25}


class ShapefileError(Exception):
    pass


# ── DBF attributes ─────────────────────────────────────────────────────────

def read_dbf(path: Path) -> tuple[list[tuple], list[dict]]:
    """Read a dBase III/IV table into a list of dicts."""
    data = path.read_bytes()
    if len(data) < 32:
        raise ShapefileError(f"{path.name}: file is too short to be a DBF")

    record_count = struct.unpack("<I", data[4:8])[0]
    header_len, record_len = struct.unpack("<HH", data[8:12])

    fields: list[tuple] = []
    offset = 32
    while data[offset] != 0x0D:
        descriptor = data[offset:offset + 32]
        name = descriptor[0:11].split(b"\x00")[0].decode("latin-1")
        fields.append((name, chr(descriptor[11]), descriptor[16], descriptor[17]))
        offset += 32

    records = []
    for i in range(record_count):
        start = header_len + i * record_len
        row_bytes = data[start:start + record_len]
        if len(row_bytes) < record_len:
            break
        if row_bytes[0:1] == b"*":          # deleted record
            continue

        row: dict[str, Any] = {}
        pos = 1
        for name, ftype, flen, fdec in fields:
            raw = row_bytes[pos:pos + flen]
            pos += flen
            try:
                text = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                text = raw.decode("latin-1").strip()

            if not text:
                row[name] = None
            elif ftype in "NF":
                try:
                    row[name] = float(text) if fdec else int(text)
                except ValueError:
                    row[name] = text
            elif ftype == "L":
                row[name] = text.upper() in ("Y", "T")
            elif ftype == "D":
                # COD boundaries use 00000000 to mean "still valid".
                row[name] = None if text == "00000000" else text
            else:
                row[name] = text
        records.append(row)

    return fields, records


# ── Geometry ───────────────────────────────────────────────────────────────

def _signed_area(ring: list[tuple[float, float]]) -> float:
    """Shoelace area. Positive means counter-clockwise."""
    total = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _assemble_polygons(rings: list[list[tuple[float, float]]]) -> list[list]:
    """Group shapefile rings into GeoJSON polygons.

    In a shapefile, exterior rings run clockwise and holes run counter-
    clockwise, with no explicit nesting: a clockwise ring starts a new polygon
    and every counter-clockwise ring after it is one of its holes. GeoJSON
    (RFC 7946) reverses the winding, so rings are flipped on the way out.
    """
    polygons: list[list] = []
    for ring in rings:
        if len(ring) < 4:
            continue
        if _signed_area(ring) < 0:          # clockwise: a new exterior ring
            polygons.append([list(reversed(ring))])
        elif polygons:                      # counter-clockwise: a hole
            polygons[-1].append(list(reversed(ring)))
        else:
            # A hole with no exterior before it means the winding convention
            # was not followed. Treat it as an exterior ring rather than
            # discarding real geometry.
            polygons.append([ring])
    return polygons


def read_shp(path: Path) -> tuple[int, tuple, list]:
    """Read geometry records from a .shp file."""
    data = path.read_bytes()
    if len(data) < 100 or struct.unpack(">i", data[0:4])[0] != 9994:
        raise ShapefileError(f"{path.name}: not a shapefile (bad magic number)")

    file_type = struct.unpack("<i", data[32:36])[0]
    bbox = struct.unpack("<4d", data[36:68])

    shapes: list[dict | None] = []
    offset = 100
    while offset < len(data):
        _, content_len = struct.unpack(">ii", data[offset:offset + 8])
        start = offset + 8
        end = start + content_len * 2
        shape_type = struct.unpack("<i", data[start:start + 4])[0]

        if shape_type == 0:                                  # null shape
            shapes.append(None)

        elif shape_type in POINT_TYPES:
            x, y = struct.unpack("<2d", data[start + 4:start + 20])
            shapes.append({"type": "Point", "coordinates": [x, y]})

        elif shape_type in POLYGON_TYPES | POLYLINE_TYPES:
            part_count, point_count = struct.unpack("<ii", data[start + 36:start + 44])
            parts = struct.unpack(f"<{part_count}i", data[start + 44:start + 44 + 4 * part_count])
            pts_start = start + 44 + 4 * part_count
            flat = struct.unpack(f"<{2 * point_count}d",
                                 data[pts_start:pts_start + 16 * point_count])

            rings = []
            for i, first in enumerate(parts):
                last = parts[i + 1] if i + 1 < part_count else point_count
                rings.append([(flat[2 * j], flat[2 * j + 1]) for j in range(first, last)])

            if shape_type in POLYGON_TYPES:
                polygons = _assemble_polygons(rings)
                if len(polygons) == 1:
                    shapes.append({"type": "Polygon", "coordinates": polygons[0]})
                else:
                    shapes.append({"type": "MultiPolygon", "coordinates": polygons})
            elif len(rings) == 1:
                shapes.append({"type": "LineString", "coordinates": [list(p) for p in rings[0]]})
            else:
                shapes.append({"type": "MultiLineString",
                               "coordinates": [[list(p) for p in r] for r in rings]})
        else:
            raise ShapefileError(
                f"{path.name}: shape type {shape_type} is not supported. "
                f"Convert it with ogr2ogr instead.")

        offset = end

    return file_type, bbox, shapes


def check_crs(prj_path: Path) -> str | None:
    """Read the .prj and confirm the data is in geographic WGS 84.

    Everything in this project is stored in EPSG:4326. A projected input
    silently loaded as lon/lat produces coordinates in the hundreds of
    thousands, so this is checked before conversion rather than after.
    """
    if not prj_path.exists():
        return None
    wkt = prj_path.read_text(errors="replace")
    if "PROJCS" in wkt:
        raise ShapefileError(
            f"{prj_path.name}: input is projected, not geographic. Reproject "
            f"to EPSG:4326 before converting.")
    if "WGS_1984" not in wkt and "WGS 84" not in wkt:
        raise ShapefileError(f"{prj_path.name}: unexpected datum. Expected WGS 84.")
    return wkt.strip()


# ── Conversion ─────────────────────────────────────────────────────────────

def convert(shp_path: Path, out_path: Path | None = None,
            precision: int = 7) -> Path:
    """Convert one shapefile to GeoJSON.

    Coordinates are rounded to `precision` decimal places. Seven gives about
    11 mm at the equator, well beyond the accuracy of any administrative
    boundary, and removes a third of the file size.
    """
    base = shp_path.with_suffix("")
    check_crs(base.with_suffix(".prj"))

    _, records = read_dbf(base.with_suffix(".dbf"))
    _, bbox, shapes = read_shp(shp_path)

    if len(records) != len(shapes):
        raise ShapefileError(
            f"{shp_path.name}: {len(records)} attribute rows but {len(shapes)} "
            f"geometries. The .dbf and .shp do not match.")

    def round_coords(obj):
        if isinstance(obj, (int, float)):
            return round(obj, precision)
        return [round_coords(o) for o in obj]

    features = []
    for props, geom in zip(records, shapes, strict=False):
        if geom is None:
            continue
        geom = {**geom, "coordinates": round_coords(geom["coordinates"])}
        clean = {k.lower(): v for k, v in props.items() if v is not None}
        features.append({"type": "Feature", "geometry": geom, "properties": clean})

    collection = {
        "type": "FeatureCollection",
        "name": base.name,
        "bbox": [round(v, precision) for v in bbox],
        "features": features,
    }

    out_path = out_path or base.with_suffix(".geojson")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shapefiles", nargs="+", type=Path)
    parser.add_argument("--outdir", type=Path, help="write output here instead of alongside the input")
    parser.add_argument("--precision", type=int, default=7)
    args = parser.parse_args()

    for shp in args.shapefiles:
        out = args.outdir / (shp.stem + ".geojson") if args.outdir else None
        try:
            written = convert(shp, out, args.precision)
        except ShapefileError as exc:
            print(f"  skipped {shp.name}: {exc}")
            continue
        size_mb = written.stat().st_size / 1e6
        print(f"  {shp.name} -> {written.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
