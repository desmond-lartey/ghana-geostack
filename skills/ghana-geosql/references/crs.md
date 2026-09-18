# Coordinate Systems - Ghana

Ghana sits on both sides of the prime meridian, which means no single UTM zone
covers it cleanly. That one fact causes most of the CRS confusion in Ghanaian
GIS work, so it is worth being explicit about the rules this project follows.

## The three rules

1. **Store in EPSG:4326.** Every geometry column in `core`, `analysis`, `h3`
   and `serve` is lon/lat. Web maps, GeoParquet, tiles and the API all expect
   it, and mixing storage CRS across themes is the commonest cause of joins
   that silently return zero rows.
2. **Measure in EPSG:32630.** Every area, length, distance and buffer is
   computed after transforming to WGS 84 / UTM 30N.
3. **Never measure in degrees.** `ST_Area` on a 4326 geometry returns square
   degrees. The number looks plausible and is meaningless. Use the
   `core.gh_*` helpers, which transform for you.

## Why 32630 and not something else

| Option | Verdict |
| --- | --- |
| **EPSG:32630** - WGS 84 / UTM 30N | **The default here.** Covers Ghana west of 0°, which is most of it. The eastern strip (Volta, Oti, out to ~1.25°E) sits past the nominal half-zone, giving scale error up to roughly 0.1%. On a 1 km measurement that is a metre. Fine for buffers, densities, accessibility and areas. |
| EPSG:32631 - UTM 31N | Correct for analysis confined to east of 0°. Splitting the country across two zones to gain 0.1% is not worth the join complexity. |
| EPSG:2136 - Accra / Ghana National Grid | The legacy national grid, in Gold Coast feet on the Accra datum. Still what a lot of cadastral and survey material is in. |
| EPSG:2137 - Accra / TM 1 NW | Metres, central meridian 1°W, which is close to Ghana's centre - the best national metric fit on paper. Accra datum, so a datum shift is needed to reconcile it with WGS 84. |
| A custom Albers or Lambert | Overkill for a country this size. |

**If your work is legal, cadastral or survey-grade**, do not take the national
grid parameters from this file or from a random EPSG lookup. Confirm the
definition and the datum transformation with the Lands Commission Survey and
Mapping Division. Datum shifts between Accra datum and WGS 84 can run to tens
of metres, which is the difference between a plot boundary and a dispute.

## Transforming

```sql
-- PostGIS
SELECT ST_Transform(geom, 32630) FROM core.building;
SELECT core.gh_area_m2(geom) FROM core.building;   -- preferred
```

```sql
-- DuckDB needs both ends named
SELECT ST_Transform(geom, 'EPSG:4326', 'EPSG:32630') FROM ghana.building;
```

```python
# GeoPandas
gdf = gdf.to_crs(32630)
gdf["area_m2"] = gdf.area
gdf = gdf.to_crs(4326)          # always store back in 4326
```

## Diagnosing a CRS problem

| Symptom | Almost always |
| --- | --- |
| Features in the Gulf of Guinea near 0,0 | Missing coordinates read as zero, or an unset CRS |
| Ghana appears in the Indian Ocean | Latitude and longitude swapped |
| Areas around 0.0001 | Measured in square degrees |
| Areas around 10⁹ too large | Measured in a projected CRS and reported as if 4326, or a unit mix-up |
| Two layers that should overlap do not | Different SRIDs; check `geometry_columns` |
| Coordinates in the hundreds of thousands | Already projected - do not transform again |

`db/qc/checks.sql` tests for the first two automatically on every build.

## The other unit trap

OSM's `height` tag is free text and inconsistent: `12`, `12 m`, `40 ft`,
`3 floors`. The transform in `db/transform/buildings.sql` keeps only clean
numbers and discards the rest rather than guessing. A building height of 40 in
Ghana is usually feet parsed as metres - the QC suite flags anything above
120 m for that reason.
