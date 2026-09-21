# DuckDB Reference — Ghana GeoStack

DuckDB is the portable path: no server, no credentials, reads GeoParquet
directly, runs on a laptop and in the browser. Use it for remote Overture
queries, for anyone without Docker, and for a second opinion on a PostGIS
result.

## Start

```bash
duckdb -init duckdb/bootstrap.sql
```

That loads `spatial`, `httpfs`, `parquet`, `json` and the community `h3`
extension, and creates views over the exports in `data/exports/`.

## Macros mirroring the PostGIS helpers

`gh_bbox()`, `gh_area_m2(g)`, `gh_length_m(g)`, `gh_distance_m(a, b)` — same
names, same meaning, so a query can usually be moved between engines by
changing only the table references.

## Differences from PostGIS that will catch you out

| | PostGIS | DuckDB spatial |
| --- | --- | --- |
| Transform | `ST_Transform(g, 32630)` | `ST_Transform(g, 'EPSG:4326', 'EPSG:32630')` |
| Spatial index | GIST, automatic | R-tree, or bbox columns in Parquet |
| `&&` operator | yes | use `ST_Intersects_Extent(a, b)` |
| Geometry from WKB | implicit | `ST_GeomFromWKB(col)` on raw Parquet |
| Rasters | `postgis_raster` | none — use GDAL or the Python path |

DuckDB's transform expects explicit source and target CRS strings. Omitting the
source is the most common porting error and produces coordinates in the wrong
hemisphere.

## Querying Overture for Ghana

Read remotely. Gate on the bbox struct **before** any spatial predicate —
that is a partition prune, not a filter, and it is the difference between
seconds and hours.

```sql
SELECT count(*)
FROM read_parquet(
  's3://overturemaps-us-west-2/release/2025-08-20.0/theme=buildings/type=building/*',
  hive_partitioning = 1)
WHERE bbox.xmax >= -3.30 AND bbox.xmin <= 1.25
  AND bbox.ymax >=  4.50 AND bbox.ymin <= 11.20;
```

**Overlap, not containment.** The feature's box must overlap Ghana's box:

```
CORRECT     bbox.xmax >= west   AND bbox.xmin <= east
WRONG       bbox.xmin >= west   AND bbox.xmax <= east
```

Containment silently drops every feature crossing the boundary — every road
leaving the country, every coastal polygon.

Always count before you extract. Always pin the release string; `latest` is
not reproducible and the schema changes between releases.

## Joining PostGIS from DuckDB

```sql
INSTALL postgres; LOAD postgres;
ATTACH 'host=localhost dbname=ghana user=ghana password=ghana'
    AS pg (TYPE postgres, READ_ONLY);

SELECT count(*) FROM pg.core.building;
```

The obvious use: run the same aggregate in both engines and confirm they
agree. If they do not, one of them is reading stale data.

## H3

```sql
SELECT h3_latlng_to_cell_string(ST_Y(ST_Centroid(geom)),
                                ST_X(ST_Centroid(geom)), 7) AS h3,
       count(*) AS buildings
FROM ghana.building
GROUP BY 1;
```

Latitude first, longitude second. Reversing them is silent and puts Ghana in
the Indian Ocean. Resolution 5 national, 7 regional, 9 urban.

## Exporting

```sql
COPY (SELECT ...) TO 'out.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY (SELECT ...) TO 'out.geojson' (FORMAT GDAL, DRIVER 'GeoJSON');
COPY (SELECT ...) TO 'out.fgb'     (FORMAT GDAL, DRIVER 'FlatGeobuf');
```

FlatGeobuf is the better choice for large vector data going into QGIS —
streamable and indexed, where GeoJSON is neither.
