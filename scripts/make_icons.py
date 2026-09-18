"""Generate the site icons from the national boundary.

The favicon is Ghana's actual outline, simplified from
`data/reference/gha_admin0.geojson`, rather than a generic pin. It is derived
from the same COD boundary the rest of the platform uses, so the mark and the
data agree.

Outputs:
    docs/assets/favicon.svg        documentation favicon
    docs/assets/logo.svg           header logo, drawn to sit on the orange bar
    docs/assets/favicon-32.png     fallback for older browsers
    docs/assets/apple-touch-icon.png
    web/favicon.svg                map viewer

Usage:
    python scripts/make_icons.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "data" / "reference" / "gha_admin0.geojson"
DOCS_ASSETS = ROOT / "docs" / "assets"
WEB = ROOT / "web"

ORANGE = "#F2683C"
INK = "#1F242B"


def douglas_peucker(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    """Simplify a ring. A favicon is 16 px across; 300 vertices is 280 wasted."""
    if len(points) < 3:
        return points

    def distance(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(x - x1, y - y1)
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]

    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        worst, index = 0.0, first
        for i in range(first + 1, last):
            d = distance(points[i], points[first], points[last])
            if d > worst:
                worst, index = d, i
        if worst > epsilon:
            keep[index] = True
            stack += [(first, index), (index, last)]

    return [p for p, k in zip(points, keep) if k]


def outline(size: int = 32, padding: float = 2.0) -> tuple[list[tuple[float, float]], float]:
    """Return the national outline scaled into a square viewBox."""
    data = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    geometry = data["features"][0]["geometry"]

    polygons = (geometry["coordinates"] if geometry["type"] == "MultiPolygon"
                else [geometry["coordinates"]])

    # The mainland is the largest ring; islands and sandbars only add noise at
    # this size.
    ring = max((polygon[0] for polygon in polygons), key=len)
    ring = [(x, y) for x, y in ring]
    ring = douglas_peucker(ring, 0.012)

    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    width, height = max(xs) - min(xs), max(ys) - min(ys)

    # Latitude degrees are longer than longitude degrees at Ghana's latitude,
    # so the outline is scaled with that correction or the country comes out
    # squashed.
    lat_mid = (max(ys) + min(ys)) / 2
    width *= math.cos(math.radians(lat_mid))

    span = max(width, height)
    scale = (size - padding * 2) / span

    offset_x = (size - width * scale) / 2
    offset_y = (size - height * scale) / 2

    points = [
        (offset_x + (x - min(xs)) * math.cos(math.radians(lat_mid)) * scale,
         size - offset_y - (y - min(ys)) * scale)       # SVG y grows downward
        for x, y in ring
    ]
    return points, scale


def svg_path(points: list[tuple[float, float]]) -> str:
    head = f"M{points[0][0]:.2f} {points[0][1]:.2f}"
    rest = "".join(f"L{x:.2f} {y:.2f}" for x, y in points[1:])
    return head + rest + "Z"


def write_svg(path: Path, size: int, fill: str, background: str | None,
              radius: float = 0) -> None:
    points, _ = outline(size, padding=size * 0.09)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}" role="img" aria-label="Ghana">'
    ]
    if background:
        parts.append(
            f'<rect width="{size}" height="{size}" rx="{radius}" fill="{background}"/>')
    parts.append(f'<path d="{svg_path(points)}" fill="{fill}"/>')
    parts.append("</svg>")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts), encoding="utf-8")
    print(f"  {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def write_png(path: Path, size: int, fill: str, background: str | None) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  Pillow not installed, skipping PNG icons")
        return

    supersample = 4
    canvas = size * supersample
    points, _ = outline(canvas, padding=canvas * 0.09)

    image = Image.new("RGBA", (canvas, canvas), background or (0, 0, 0, 0))
    ImageDraw.Draw(image).polygon(points, fill=fill)
    image = image.resize((size, size), Image.LANCZOS)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    print(f"  {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def main() -> None:
    print("Generating icons from the national boundary")

    # Documentation: the outline in orange, transparent behind it, so it reads
    # on both the orange header bar and a browser tab of any colour.
    write_svg(DOCS_ASSETS / "favicon.svg", 32, ORANGE, None)
    write_svg(DOCS_ASSETS / "logo.svg", 32, "#FFFFFF", None)
    write_png(DOCS_ASSETS / "favicon-32.png", 32, ORANGE, None)
    write_png(DOCS_ASSETS / "apple-touch-icon.png", 180, ORANGE, INK)

    # Map viewer.
    write_svg(WEB / "favicon.svg", 32, ORANGE, None)
    write_png(WEB / "favicon-32.png", 32, ORANGE, None)
    write_png(WEB / "apple-touch-icon.png", 180, ORANGE, INK)


if __name__ == "__main__":
    main()
