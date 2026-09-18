# Querying in the browser

Every visitor to the map can run SQL. No account, no install, no server: the
query engine is DuckDB compiled to WebAssembly, running in the page, reading
data the page already downloaded.

## What is available

| View | Rows | Contents |
| --- | ---: | --- |
| `ghana.region` | 16 | Regions |
| `ghana.district` | 260 | Districts (MMDAs) |
| `ghana.capital` | 177 | Administrative capitals |
| `ghana.building`, `ghana.road`, `ghana.facility` | — | Only once the pipeline has been run and exported |

Every row carries, in addition to its source attributes:

| Column | Meaning |
| --- | --- |
| `lon`, `lat` | Centroid, computed area-weighted so it falls inside concave shapes |
| `bbox_xmin`, `bbox_ymin`, `bbox_xmax`, `bbox_ymax` | Bounding box |
| `area_sqkm` | Area, already in square kilometres |
| `geom` | The geometry as GeoJSON text |

## Two levels of spatial capability

The viewer tries to load the DuckDB spatial extension on start. When it
succeeds, every view gains a `shape` column holding a real geometry and the
full `ST_` function set applies to it. When it fails — offline, behind a strict
proxy, or on an engine build without the extension — everything below still
works, because it does not depend on the extension at all.

The status line under the query box says which mode you are in.

`geom` is always GeoJSON text regardless, so drawing a result behaves
identically either way.

## Spatial SQL without the extension

The spatial attributes above are precomputed as each layer loads, and the
operations people actually need are provided as plain SQL macros:

| Macro | Returns |
| --- | --- |
| `gh_distance_km(lat1, lon1, lat2, lon2)` | Great-circle distance in kilometres |
| `gh_within_km(lat1, lon1, lat2, lon2, km)` | Boolean |
| `gh_bbox_overlaps(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2)` | Boolean |
| `gh_in_bbox(lon, lat, xmin, ymin, xmax, ymax)` | Boolean |
| `gh_bearing(lat1, lon1, lat2, lon2)` | Degrees from north |

These are ordinary macros, so they work in the browser and in the desktop
build alike.

### Worked examples

Districts within 100 km of Accra, nearest first, ready to draw:

```sql
SELECT adm2_name, adm1_name,
       round(gh_distance_km(5.603, -0.187, lat, lon), 1) AS km,
       geom
FROM ghana.district
WHERE gh_within_km(5.603, -0.187, lat, lon, 100)
ORDER BY km;
```

The districts furthest from any regional capital:

```sql
SELECT district, capital, km FROM (
  SELECT d.adm2_name AS district, c.name AS capital,
         round(gh_distance_km(d.lat, d.lon, c.lat, c.lon), 1) AS km,
         row_number() OVER (
           PARTITION BY d.adm2_name
           ORDER BY gh_distance_km(d.lat, d.lon, c.lat, c.lon)) AS rn
  FROM ghana.district d
  CROSS JOIN ghana.capital c
  WHERE c.adm_p_lvl = 1
)
WHERE rn = 1
ORDER BY km DESC
LIMIT 20;
```

Districts per region, joined on p-codes:

```sql
SELECT r.adm1_name AS region, count(*) AS districts,
       round(sum(d.area_sqkm)) AS km2
FROM ghana.district d
JOIN ghana.region r ON r.adm1_pcode = left(d.adm2_pcode, 4)
GROUP BY 1 ORDER BY districts DESC;
```

### When the extension is unavailable

True geometric predicates — point-in-polygon against a real boundary, polygon
intersection, buffering, overlay — need `shape`, and therefore the extension.
Bounding-box tests approximate containment well enough for filtering, but they
are not the same operation and should not be described as one.

For guaranteed spatial work, use the desktop build:

```bash
duckdb -init duckdb/bootstrap.sql
```

Or query PostGIS directly, which is the authoritative store.

## Drawing a result

Include `geom` in the select list and press **Show on map**. Points, lines and
polygons all render, the map fits to the result, and the attributes appear in
the popup. Leave `geom` out and the button says so rather than failing
silently.

## Downloading a result

**GeoJSON** and **CSV** buttons sit beside **Show on map**. GeoJSON needs
`geom` in the select list and opens directly in QGIS; CSV covers everything
else. Both are produced in the browser from the result already in hand.

## Asking in plain English

The **Ask** tab turns a question into SQL, shows the SQL, and runs it only
after you have read it. Three ways it can be answered, in order:

1. **The reader's own API key.** Saved under **Map → Asking questions**, kept
   in that browser. Anthropic, OpenAI, Google Gemini, or any OpenAI-compatible
   endpoint via a custom base URL. Nothing passes through this site.
2. **The site's endpoint.** `api/ask.js`, enabled by setting
   `ANTHROPIC_API_KEY` on the deployment. Visitors need nothing.
3. **Built-in patterns.** Counts, rankings, districts within a named region.
   Works offline with no key anywhere.

In all three cases the query itself runs in the reader's browser against data
already downloaded. Only the question ever travels; no row of the database
leaves the machine.

The model is told the schema, the macros, and that `ST_` functions do not
exist, so it writes SQL that runs here rather than SQL that would need a
server.


## What is checked before generated SQL runs

SQL written by a model is not SQL the reader wrote, so it is validated before
execution: string and comment literals are masked, then the statement must open
with `SELECT` or `WITH` and contain no side-effecting keyword anywhere. That
second condition is what catches a data-modifying CTE such as
`WITH x AS (DELETE ...) SELECT * FROM x`.

SQL typed by hand in the Query tab is not checked. That database lives in the
reader's own browser and is discarded on reload.

The approach is adapted from
[GeoLibre](https://github.com/opengeos/GeoLibre)'s assistant guard.

## Geoprocessing in the browser

The **Tools** tab runs vector operations on features already in the page. The
library is loaded on first use, so a visitor who never opens the tab never
downloads it.

| Tool | Does | Needs a parameter |
| --- | --- | --- |
| Buffer | A zone of the given radius around each feature | Radius in km |
| Centroids | One point per feature, at its centre of mass | — |
| Dissolve into one | Merges every feature into a single polygon | — |
| Convex hull | The tightest convex polygon containing the input | — |
| Bounding box | One rectangle around the whole input | — |
| Simplify | Removes vertices while keeping the shape | Tolerance in degrees |
| Voronoi catchments | The area closest to each input point | — |
| Measure | Area in km² and perimeter in km per feature | — |

Input is either the current query result or a whole layer. Output draws on the
map, appears as a table, and downloads as GeoJSON.

### A worked example

Health facility catchments, without leaving the browser:

1. Query tab: `SELECT name, adm1_name, geom FROM ghana.capital WHERE adm_p_lvl = 1;`
2. Tools tab: input **Current query result**, tool **Buffer**, radius **50**
3. Run. Sixteen catchments draw on the map and download as GeoJSON.

Swap in `ghana.facility` once the pipeline has been run, set the radius to 5,
and that is the CHPS catchment analysis — computed on the reader's own machine.

### What these results are, and are not

The library works on the sphere and its buffers, unions and intersections are
approximations. They are correct enough to explore with, to sketch a catchment,
to see whether an idea is worth pursuing.

They are not the authority. Anything that has to be defensible — a published
figure, a planning submission, a decision about where a clinic goes — should be
recomputed in PostGIS, where the projection is explicit, the geometry is valid,
and the result passes the quality-control suite.

Voronoi catchments deserve that caveat twice over: they divide space by
straight-line proximity alone, ignoring roads, rivers and the rainy season. In
Ghana that is a large simplification, and the map should say so.

## Live data from OpenStreetMap

The layers marked *needs database* come from the full pipeline. A visitor who
has no database can still fill the same ground: the **Layers** tab has a *Live
from OpenStreetMap* section that fetches features for the current view from the
Overpass API. No account, no key.

| Layer | Contents | View must be under |
| --- | --- | ---: |
| Health facilities | Hospitals, clinics, doctors, pharmacies, health posts | 60,000 km² |
| Schools | Schools, colleges, universities, kindergartens | 60,000 km² |
| Markets and shops | Marketplaces, supermarkets, fuel stations | 30,000 km² |
| Water points | Boreholes, wells, taps, pumps | 30,000 km² |
| Roads | Motorway to tertiary | 4,000 km² |
| Buildings | Footprints | 120 km² |

The area limits exist because Overpass is a free public service run on donated
hardware. A national building query would be refused by it and would deserve to
be. Zoom to the area you care about first.

### Fetched data becomes a table

A fetch does not only draw. Each result is registered as a table, so the Query
tab and the Tools tab treat it exactly like a published layer:

```sql
SELECT name, amenity, lon, lat, geom
FROM ghana.osm_health
ORDER BY name;
```

Which means the full chain works with no database at all — fetch health
facilities for a district, buffer them by 5 km in the Tools tab, and download
the catchments as GeoJSON.

Tables created this way: `ghana.osm_health`, `ghana.osm_education`,
`ghana.osm_market`, `ghana.osm_water`, `ghana.osm_road`, `ghana.osm_building`.
They last for the session and are gone on reload.

### Licence

OpenStreetMap data is ODbL. A derived database published from it must also be
ODbL, and attribution is required either way:

> © OpenStreetMap contributors, ODbL

### Coverage is uneven

OSM coverage in Ghana is good in Accra and Kumasi and thinner elsewhere. The
absence of a clinic from a fetched result means nobody has mapped one there,
not that none exists. Where a result looks sparse, say so on the map rather
than letting a reader infer a gap in provision from a gap in the data.

### Running your own endpoint

The public instance is rate-limited and occasionally busy. Point the viewer at
another by changing one meta tag:

```html
<meta name="gh:overpass-url" content="https://your-overpass.example.org/api/interpreter">
```

A self-hosted Overpass instance loaded with the Geofabrik Ghana extract removes
the rate limit and the area caps entirely.
