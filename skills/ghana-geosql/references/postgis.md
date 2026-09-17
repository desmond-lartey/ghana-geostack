# PostGIS Reference — Ghana GeoStack

## Connect

```bash
psql -h ${PGHOST:-localhost} -p ${PGPORT:-5432} -U ${PGUSER:-ghana} -d ${PGDATABASE:-ghana}
```

If that fails, the database is not running. `docker compose -f docker/docker-compose.yml up -d`.

## Discover

```sql
-- What exists, and whether it can be published
SELECT id, title, theme, schema_name, table_name,
       feature_count, srid, licence, publishable
FROM meta.dataset ORDER BY theme, title;

-- Every geometry column with its SRID and type
SELECT f_table_schema, f_table_name, f_geometry_column, type, srid
FROM geometry_columns
WHERE f_table_schema IN ('core','analysis','h3','serve')
ORDER BY 1, 2;

-- Columns of one table
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'core' AND table_name = 'building'
ORDER BY ordinal_position;

-- Last quality-control verdict
SELECT * FROM meta.qc_latest ORDER BY errors DESC, target;
```

## Ghana helpers

Defined in `db/migrations/003_ghana_functions.sql`. Use them rather than
rolling your own transform every time.

| Function | Returns |
| --- | --- |
| `core.gh_bbox()` | Ghana envelope, EPSG:4326 |
| `core.gh_metric_srid()` | 32630 |
| `core.gh_area_m2(geom)` | Area in m², transformed correctly |
| `core.gh_length_m(geom)` | Length in metres |
| `core.gh_distance_m(a, b)` | Distance in metres |
| `core.gh_buffer_m(geom, m)` | Buffer by metres, returned in 4326 |
| `core.gh_normalise_name(text)` | Lowercase, unaccented, punctuation-stripped |
| `core.gh_clean(geom)` | Make valid, keep the original dimension |

## The two-filter pattern

```sql
WITH area AS (SELECT geom FROM core.admin_district WHERE id = 'GHA.5.3_1')
SELECT b.id, b.height_m::real AS height_m, b.geom
FROM core.building b, area a
WHERE b.geom && a.geom
  AND ST_Intersects(b.geom, a.geom);
```

`&&` uses the GIST index and prunes candidates. `ST_Intersects` is exact.
Both. Every time.

## Nearest neighbour

`<->` with `ORDER BY ... LIMIT n` is an index-ordered scan. Without it, a
nearest-facility query over millions of buildings is a cross join.

```sql
SELECT b.id,
       f.name,
       core.gh_distance_m(b.geom, f.geom) AS dist_m
FROM core.building b
CROSS JOIN LATERAL (
    SELECT f.name, f.geom
    FROM core.facility f
    WHERE f.category = 'health'
    ORDER BY b.geom <-> f.geom
    LIMIT 1
) f
WHERE b.district_id = 'GHA.5.3_1';
```

`<->` orders by planar degree distance. Over a few kilometres at Ghana's
latitudes the ranking matches metric distance. For a guaranteed-exact result,
take the 5 nearest by `<->` and pick the minimum metric distance from those.

## Rasters

```sql
-- Elevation at a point
SELECT ST_Value(rast, ST_SetSRID(ST_Point(-0.187, 5.603), 4326))
FROM core.dem
WHERE ST_Intersects(rast, ST_SetSRID(ST_Point(-0.187, 5.603), 4326));

-- Statistics within a polygon
SELECT (ST_SummaryStats(ST_Clip(d.rast, r.geom, true))).*
FROM core.dem d
JOIN core.admin_region r ON r.id = 'GH-AH'
WHERE ST_Intersects(d.rast, r.geom);
```

If `ST_Value` errors about GDAL drivers, raster access is disabled:
`SET postgis.gdal_enabled_drivers = 'ENABLE_ALL';`

## CREATE TABLE AS loses the SRID

`CREATE TABLE ... AS SELECT` does not register the SRID in `geometry_columns`,
so QC will report SRID 0 on a table that looks fine. Fix it in the same
transaction:

```sql
SELECT UpdateGeometrySRID('analysis', 'my_table', 'geom', 4326);
```

Better: declare the column type in the SELECT — `geom::geometry(Polygon, 4326)`.

## Performance

- `ANALYZE` after every bulk load. The planner will pick a sequential scan
  over a perfectly good GIST index if the statistics are stale.
- `core.building` is partitioned by `region_id`. Include it in the WHERE clause
  and the planner touches one partition instead of sixteen.
- For repeated heavy analysis, materialise rather than re-running a view.
- `EXPLAIN (ANALYZE, BUFFERS)` before optimising anything. Guessing wastes
  more time than measuring.
