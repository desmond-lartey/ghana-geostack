---
name: ghana-geosql
description: Write, validate and map spatial SQL against the Ghana GeoStack database (PostGIS and DuckDB). Discovers the schema, resolves Ghanaian place names, validates every result in SQL before presenting it, and renders maps.
user-invocable: true
---

# Ghana GeoSQL

Adapted from [dekart-xyz/geosql](https://github.com/dekart-xyz/geosql) (MIT) and
retargeted at one country and one database.

The workflow is the point: **discover, resolve, draft, validate, then map.**
Steps 1 to 4 happen before the user sees a query. Validation is not optional
and it is done in SQL, not by looking at the output and deciding it seems
about right.

## Engines

| Engine | When to use it | Connection |
| --- | --- | --- |
| PostGIS | The default. Authoritative data, rasters, routing, anything written back. | `psql` with `$PGHOST`, `$PGDATABASE` |
| DuckDB | No server available, remote GeoParquet, Overture, quick local analysis. | `duckdb -init duckdb/bootstrap.sql` |

Check what is available before assuming:

```bash
for c in psql duckdb ogr2ogr dekart; do command -v $c >/dev/null && echo "$c=ok" || echo "$c=missing"; done
psql -c 'SELECT postgis_full_version();' 2>/dev/null | head -1
```

If neither engine is reachable, say so and stop. Do not invent results.

Dialect references, read the one that matches the engine:

- PostGIS: `references/postgis.md`
- DuckDB: `references/duckdb.md`
- What data exists and what it means: `references/data-catalog.md`
- Coordinate systems: `references/crs.md`
- Map styling: `references/map-styling.md`

## Step 1 — Discover the schema

Never assume a table or column name. Read the catalogue first:

```sql
SELECT id, title, theme, schema_name, table_name, feature_count,
       licence, publishable
FROM meta.dataset
ORDER BY theme, title;
```

Then confirm columns for the tables you will actually touch:

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'core'
ORDER BY table_name, ordinal_position;
```

If `meta.dataset` is empty the database has not been loaded. Say that plainly
and point at `make pipeline` rather than writing a query against nothing.

## Step 2 — Resolve the place

Ghanaian place names are ambiguous and inconsistently spelled across sources.
Resolve them against the database before filtering on them, always.

**Join on p-codes, never on names.** Every unit carries one, they are stable
across releases, and the hierarchy is encoded in the code: `GH07` is Greater
Accra, and `GH0701` is a district within it. A district's parent is
`left(id, 4)`, so the hierarchy needs no spatial join.

**The traps, in order of how often they bite:**

- **Accra is not a district.** It may mean Greater Accra Region (`GH07`,
  ~3,699 km²), Accra Metropolitan Assembly (~140 km²), or the built-up area.
  These differ by more than an order of magnitude. Ask, or resolve explicitly
  and state which was used.
- **Region names collide with district names.** Filter `core.admin_region` for
  regions and `core.admin_district` for districts, and say which was used.
- **The 2019 reorganisation.** Six regions were created in 2018-19. A result
  containing Brong Ahafo, or returning 10 regions, is reading a superseded
  boundary set. The current configuration is 16 regions and 260 districts.
- **Spelling.** Sekondi-Takoradi or Sekondi Takoradi; Ashanti or Asante. The
  boundary source spells North East as "Northern East". Match through
  `core.gh_normalise_name()` and check `core.admin_alias`.

```sql
-- Resolve a name to a unit, including aliases and superseded names
SELECT g.level, g.place_id, g.place_name, g.parent_name, g.area_km2
FROM core.gazetteer g
WHERE g.place_norm LIKE '%' || core.gh_normalise_name('ashanti') || '%'
   OR g.place_id IN (SELECT pcode FROM core.admin_alias
                     WHERE alias_norm LIKE '%' || core.gh_normalise_name('ashanti') || '%')
ORDER BY g.level, g.area_km2 DESC;
```

Take the exact bbox from the resolved geometry and use full precision. Do not
round it, and do not type coordinates from memory:

```sql
SELECT ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)
FROM core.admin_region WHERE id = 'GH02';   -- Ashanti
```

## Step 3 — Draft the query

**Both filters, every time.** The bounding-box operator `&&` is
index-accelerated and prunes the scan. `ST_Intersects` is the exact test. `&&`
alone over-selects, because a bounding box is a rectangle and a region is not.

```sql
WITH area AS (
    SELECT geom FROM core.admin_region WHERE id = 'GH02'   -- Ashanti
)
SELECT b.id, b.height_m, b.geom
FROM core.building b, area a
WHERE b.geom && a.geom              -- index gate
  AND ST_Intersects(b.geom, a.geom) -- exact test
LIMIT 1000;
```

Other rules that matter here:

- **Measure in metres, never in degrees.** `ST_Area` and `ST_Length` on a 4326
  geometry return square degrees and degrees. Use `core.gh_area_m2()`,
  `core.gh_length_m()`, `core.gh_distance_m()`, or transform to 32630 yourself.
  This is the single most common error in spatial SQL, and it is dangerous
  because the numbers look reasonable.
- **Select named columns.** Never `SELECT *` into a map layer; Overture-derived
  tables carry nested structs that break renderers.
- **Cast 64-bit integers before binding them to a visual channel.** Colour,
  height and radius channels choke on `bigint`. Use `::real` or `::int`.
- **Filter machine-derived buildings on confidence** (`>= 0.7`) unless the
  question is specifically about model output.
- **Query `core`, not `raw`.** `raw` is unconformed and its columns change with
  the source.

## Step 4 — Validate. Not optional.

Do not show the user a query or a map until every check below has run and the
numbers are plausible for Ghana.

1. **Row count.** `SELECT count(*)`. Zero means debug, not present. A count
   equal to a `LIMIT` you set means the result is truncated — say so.
2. **Magnitude.** For polygons, total area in km². For lines, total length in
   km. In metres, via a transform. A correct row count with wrong geometry is
   invisible to a count and obvious to this check.
3. **Extent.** Confirm the result sits inside Ghana:
   `SELECT count(*) FROM (...) t WHERE NOT (geom && core.gh_bbox());` — anything
   other than zero means a CRS or coordinate-order problem.
4. **Nulls in the columns you are about to map.** A colour ramp bound to a
   mostly-null column renders as a blank layer and looks like a styling bug.
5. **Plausibility, against Ghana's real numbers.** Use the reference figures
   below. If the result contradicts them, debug before presenting.

```sql
-- The standard validation block. Run it on every result.
WITH result AS ( /* your query */ )
SELECT
    count(*)                                             AS rows,
    round(sum(core.gh_area_m2(geom))::numeric / 1e6, 2)  AS total_km2,
    count(*) FILTER (WHERE geom IS NULL)                 AS null_geom,
    count(*) FILTER (WHERE NOT (geom && core.gh_bbox())) AS outside_ghana,
    min(ST_XMin(geom))::numeric(8,4)                     AS xmin,
    max(ST_XMax(geom))::numeric(8,4)                     AS xmax
FROM result;
```

### Reference figures for Ghana

Use these to sanity-check. They are order-of-magnitude guards, not precise
truth, and should be cited as approximate.

| Quantity | Approximate value |
| --- | --- |
| Land area | 238,533 km² |
| Coastline | ~539 km |
| Regions | 16 (since 2019), p-coded GH01–GH16 |
| Districts / MMDAs | 260, p-coded GHrrdd |
| Boundary area, COD set | 239,473 km² across regions and districts alike |
| Population (2021 PHC) | ~30.8 million |
| Highest point | Mount Afadja, ~885 m |
| Largest region by area | Savannah, ~35,863 km² |
| Most populous region | Greater Accra, ~5.4 million |
| Accra Metropolitan Assembly | ~140 km² |
| Greater Accra Region | ~3,699 km² |
| Lake Volta surface | ~8,500 km² |

If a query says a district is larger than the region containing it, or that
Ghana's road network is 400 km long, or that elevation reaches 3,000 m, the
query is wrong. Say so and fix it rather than presenting it with a caveat.

## Step 5 — Map

A map catches what a row count cannot: features in the sea, a missing region,
duplicated geometry, a choropleth that is really a population map.

Three rendering paths, in order of preference:

1. **The built-in viewer.** `make serve` then open `web/index.html`. Point it
   at a `serve.*` view or paste SQL into the console.
2. **Dekart**, if the user has it. `dekart` CLI, PostGIS connector, then
   snapshot and inspect the PNG before calling the map done. Full flow in
   `references/map-styling.md`.
3. **GeoJSON export** for QGIS, when the user prefers a desktop GIS.

Whichever path, **look at the rendered map before describing it.** Do not
narrate visual insights from row counts. If you have not seen the render, say
what the numbers show and stop there.

Styling rules are in `references/map-styling.md`. The ones people get wrong:

- Choropleth by district misleads in Ghana, because district areas vary by two
  orders of magnitude. Prefer H3 hexes or a rate rather than a count.
- Sequential palettes for magnitude, diverging only when there is a real
  midpoint, qualitative for eight categories at most. Never rainbow.
- Dark basemap for point density, light for choropleths.
- Always label the map with its data source and date. Every layer here carries
  an attribution string in `meta.dataset` — use it.

## Governance, which applies to every answer

- **Check `publishable` before exporting or tiling anything.** A dataset with
  `publishable = false` has an unresolved licence. GADM boundaries are
  non-commercial. OSM is ODbL share-alike.
- **Reproduce the attribution string** from `meta.dataset` on every map.
- **Never publish identifiable point data about individuals.** Health facility
  locations are public; patient-linked records are not, and rows marked
  `sensitivity = 'restricted'` do not go to a public tile or export.
- **Say what the data is, not what it would be convenient for it to be.** The
  flood layer is observed historical surface water plus low terrain. It is not
  a modelled flood risk and must not be labelled as one.

## When something is missing

- PostGIS not reachable → give the exact `docker compose up -d` command; do not
  silently switch to DuckDB without saying so.
- A table is empty → name the pipeline step that fills it.
- The `h3` extension is missing → run the rollup in DuckDB instead and say
  which engine produced the numbers.
- Data for the question does not exist in Ghana → say so, name the likely
  source from `config/sources.yml`, and offer to add it to the catalogue.
  Do not approximate an answer from a table that measures something else.
