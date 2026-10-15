/* The geometry substitute itself. See turf_stub.cjs for what is exact
   here and what is an approximation. This file is served to the page in
   place of the Turf import, so it is a module and nothing else. */

const R = 6371.0088;
const rad = (d) => (d * Math.PI) / 180;

function coordsOf(geometry) {
  if (!geometry) return [];
  const out = [];
  const walk = (c) => {
    if (typeof c[0] === "number") out.push(c);
    else for (const part of c) walk(part);
  };
  if (geometry.type === "GeometryCollection") {
    for (const g of geometry.geometries || []) out.push(...coordsOf(g));
  } else if (geometry.coordinates) {
    walk(geometry.coordinates);
  }
  return out;
}

function allCoords(input) {
  if (!input) return [];
  if (input.type === "FeatureCollection") {
    return input.features.flatMap((f) => coordsOf(f.geometry));
  }
  if (input.type === "Feature") return coordsOf(input.geometry);
  return coordsOf(input);
}

function haversine(a, b) {
  const [x1, y1] = a, [x2, y2] = b;
  const dLat = rad(y2 - y1), dLon = rad(x2 - x1);
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(y1)) * Math.cos(rad(y2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

const feature = (geometry, properties = {}) => ({ type: "Feature", properties, geometry });
const featureCollection = (features) => ({ type: "FeatureCollection", features });
const point = (coordinates, properties = {}) =>
  feature({ type: "Point", coordinates }, properties);

function bbox(input) {
  const cs = allCoords(input);
  if (!cs.length) return [0, 0, 0, 0];
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const [x, y] of cs) {
    if (x < w) w = x; if (x > e) e = x;
    if (y < s) s = y; if (y > n) n = y;
  }
  return [w, s, e, n];
}

function bboxPolygon(box) {
  const [w, s, e, n] = box;
  return feature({ type: "Polygon",
    coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] });
}

const envelope = (input) => bboxPolygon(bbox(input));

function centroid(input, options = {}) {
  const cs = allCoords(input);
  if (!cs.length) return point([0, 0], options.properties || {});
  let x = 0, y = 0;
  for (const c of cs) { x += c[0]; y += c[1]; }
  return point([x / cs.length, y / cs.length], options.properties || {});
}

function ringArea(ring) {
  // The spherical excess formula Turf uses, in square metres.
  let total = 0;
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i], [x2, y2] = ring[i + 1];
    total += rad(x2 - x1) * (2 + Math.sin(rad(y1)) + Math.sin(rad(y2)));
  }
  return Math.abs((total * 6378137 * 6378137) / 2);
}

function area(input) {
  const features = input.type === "FeatureCollection" ? input.features : [input];
  let total = 0;
  for (const f of features) {
    const g = f.geometry || f;
    const polys = g.type === "Polygon" ? [g.coordinates]
      : g.type === "MultiPolygon" ? g.coordinates : [];
    for (const poly of polys) {
      total += ringArea(poly[0]);
      for (let i = 1; i < poly.length; i += 1) total -= ringArea(poly[i]);
    }
  }
  return total;
}

const distance = (a, b) => haversine(
  a.geometry ? a.geometry.coordinates : a.coordinates || a,
  b.geometry ? b.geometry.coordinates : b.coordinates || b);

function length(input) {
  const features = input.type === "FeatureCollection" ? input.features : [input];
  let total = 0;
  for (const f of features) {
    const g = f.geometry || f;
    const lines = g.type === "LineString" ? [g.coordinates]
      : g.type === "MultiLineString" ? g.coordinates : [];
    for (const line of lines) {
      for (let i = 0; i < line.length - 1; i += 1) total += haversine(line[i], line[i + 1]);
    }
  }
  return total;
}

function inRing(pt, ring) {
  const [x, y] = pt;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function booleanPointInPolygon(pt, polygon) {
  const c = pt.geometry ? pt.geometry.coordinates : pt.coordinates || pt;
  const g = polygon.geometry || polygon;
  const polys = g.type === "Polygon" ? [g.coordinates]
    : g.type === "MultiPolygon" ? g.coordinates : [];
  for (const poly of polys) {
    if (!inRing(c, poly[0])) continue;
    let hole = false;
    for (let i = 1; i < poly.length; i += 1) if (inRing(c, poly[i])) hole = true;
    if (!hole) return true;
  }
  return false;
}

function booleanIntersects(a, b) {
  const [aw, as, ae, an] = bbox(a);
  const [bw, bs, be, bn] = bbox(b);
  return !(ae < bw || be < aw || an < bs || bn < as);
}

function convex(input) {
  const pts = allCoords(input).slice().sort((p, q) => p[0] - q[0] || p[1] - q[1]);
  if (pts.length < 3) return null;
  const cross = (o, a, b) =>
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const half = (list) => {
    const out = [];
    for (const p of list) {
      while (out.length >= 2 && cross(out[out.length - 2], out[out.length - 1], p) <= 0) out.pop();
      out.push(p);
    }
    out.pop();
    return out;
  };
  const hull = [...half(pts), ...half(pts.slice().reverse())];
  hull.push(hull[0]);
  return feature({ type: "Polygon", coordinates: [hull] });
}

function nearestPoint(target, collection) {
  let best = null, bestD = Infinity;
  for (const f of collection.features) {
    const d = distance(target, f);
    if (d < bestD) { bestD = d; best = f; }
  }
  if (best) best.properties = { ...best.properties, distanceToPoint: bestD };
  return best;
}

function pointOnFeature(input) {
  const c = centroid(input);
  const g = (input.features ? input.features[0] : input);
  const geom = g.geometry || g;
  if ((geom.type === "Polygon" || geom.type === "MultiPolygon")
      && !booleanPointInPolygon(c, geom)) {
    const first = coordsOf(geom)[0];
    return point(first);
  }
  return c;
}

/* ── The approximations. Documented at the top; do not assert on shape. ── */

function buffer(input, radius) {
  const features = input.type === "FeatureCollection" ? input.features : [input];
  const out = [];
  for (const f of features) {
    const [cx, cy] = centroid(f).geometry.coordinates;
    const dLat = radius / 110.574;
    const dLon = radius / (111.320 * Math.cos(rad(cy)) || 1);
    const ring = [];
    for (let i = 0; i <= 32; i += 1) {
      const a = (i / 32) * Math.PI * 2;
      ring.push([cx + Math.cos(a) * dLon, cy + Math.sin(a) * dLat]);
    }
    out.push(feature({ type: "Polygon", coordinates: [ring] }, { ...f.properties }));
  }
  return input.type === "FeatureCollection" ? featureCollection(out) : out[0];
}

const simplify = (input) => input;
const intersect = (collection) => {
  const [a, b] = collection.features || [];
  if (!a || !b) return null;
  return booleanIntersects(a, b) ? feature(a.geometry, {}) : null;
};
const union = (collection) => (collection.features || [])[0] ?? null;
const voronoi = () => featureCollection([]);

const TURF = {
  feature, featureCollection, point, bbox, bboxPolygon, envelope, centroid,
  area, distance, length, booleanPointInPolygon, booleanIntersects, convex,
  nearestPoint, pointOnFeature, buffer, simplify, intersect, union, voronoi
};

export {
  feature, featureCollection, point, bbox, bboxPolygon, envelope, centroid,
  area, distance, length, booleanPointInPolygon, booleanIntersects, convex,
  nearestPoint, pointOnFeature, buffer, simplify, intersect, union, voronoi
};

export default {
  feature, featureCollection, point, bbox, bboxPolygon, envelope, centroid,
  area, distance, length, booleanPointInPolygon, booleanIntersects, convex,
  nearestPoint, pointOnFeature, buffer, simplify, intersect, union, voronoi
};
