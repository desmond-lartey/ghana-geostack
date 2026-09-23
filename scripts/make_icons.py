"""Generate the site icons from the national boundary.

The mark is Ghana's actual outline, simplified from
`data/reference/gha_admin0.geojson`, rather than a generic pin. It is derived
from the same COD boundary the rest of the platform uses, so the mark and the
data agree.

Around it is a surveyor's reticle: a ring, a north mark at the top and ticks
at east, south and west. That says what the country is doing there — this is a
mapping tool, not a page about Ghana — and it is what survives at 16 px, where
the outline alone is an orange smudge.

The compass was tried *through* the outline first, which is the obvious reading
of "a compass across the shape". It does not work: any ring or needle cut
through a country that small takes the country apart, and what is left reads as
a broken blob rather than as Ghana. The reticle around it keeps both.

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

    return [p for p, k in zip(points, keep, strict=True) if k]


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


def mark(size: float) -> dict:
    """The mark as plain geometry, in one place.

    The SVG and the PNG are drawn by different libraries from this one
    description, so they cannot drift into two slightly different logos. Every
    number is a fraction of the canvas, so the mark is the same at 16 px and at
    180 px.
    """
    margin = size * 0.085                      # from the canvas edge to the ring
    stroke = size * 0.040                      # the ring, and the ticks
    radius = (size - margin * 2) / 2 - stroke / 2
    north = size * 0.155                       # the north mark, tip to base
    tick = size * 0.042                        # tick width
    reach = margin * 1.5                       # ticks run from the edge to here
    half = size / 2

    return {
        "ring": (half, half, radius, stroke),
        # The ring is broken where the north mark sits, so the two read as one
        # shape rather than a triangle resting on a line.
        "gap": (half - north * 0.8, 0.0, north * 1.6, margin + stroke * 1.5),
        "north": [(half, size * 0.008),
                  (half - north / 2, margin + north * 0.60),
                  (half + north / 2, margin + north * 0.60)],
        "ticks": [(half - tick / 2, size - reach, tick, reach),     # south
                  (0.0, half - tick / 2, reach, tick),              # west
                  (size - reach, half - tick / 2, reach, tick)],    # east
        "country": outline(size, padding=size * 0.255)[0],
    }


def write_svg(path: Path, size: int, fill: str, background: str | None,
              radius: float = 0) -> None:
    m = mark(size)
    cx, cy, r, stroke = m["ring"]
    gx, gy, gw, gh = m["gap"]
    # The mask id has to be unique on a page, because these files get inlined.
    mask_id = f"gap-{path.stem}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}" role="img" '
        f'aria-label="Ghana GeoStack">',
        f'<mask id="{mask_id}">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>'
        f'<rect x="{gx:.2f}" y="{gy:.2f}" width="{gw:.2f}" height="{gh:.2f}" fill="#000"/>'
        f'</mask>',
    ]
    if background:
        parts.append(
            f'<rect width="{size}" height="{size}" rx="{radius}" fill="{background}"/>')

    parts.append(f'<g fill="{fill}">')
    parts.append(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="none" '
        f'stroke="{fill}" stroke-width="{stroke:.2f}" mask="url(#{mask_id})"/>')
    parts.append('<path d="'
                 + "".join(f'{"M" if i == 0 else "L"}{x:.2f} {y:.2f}'
                           for i, (x, y) in enumerate(m["north"]))
                 + 'Z"/>')
    for x, y, w, h in m["ticks"]:
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"/>')
    parts.append(f'<path d="{svg_path(m["country"])}"/>')
    parts.append("</g></svg>")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts), encoding="utf-8")
    print(f"  {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def write_png(path: Path, size: int, fill: str, background: str | None) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  Pillow not installed, skipping PNG icons")
        return

    # Eight times, not four: the ring and the ticks are thin, and at 16 px a
    # coarser supersample turns them into grey mush.
    supersample = 8
    canvas = size * supersample
    m = mark(canvas)
    cx, cy, r, stroke = m["ring"]
    clear = (0, 0, 0, 0)

    image = Image.new("RGBA", (canvas, canvas), background or clear)
    draw = ImageDraw.Draw(image)

    draw.ellipse([cx - r - stroke / 2, cy - r - stroke / 2,
                  cx + r + stroke / 2, cy + r + stroke / 2],
                 outline=fill, width=round(stroke))
    gx, gy, gw, gh = m["gap"]
    draw.rectangle([gx, gy, gx + gw, gy + gh], fill=background or clear)
    draw.polygon(m["north"], fill=fill)
    for x, y, w, h in m["ticks"]:
        draw.rectangle([x, y, x + w, y + h], fill=fill)
    draw.polygon(m["country"], fill=fill)

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
