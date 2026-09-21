-- overture_ghana.sql — query Overture Maps for Ghana without downloading it.
--
-- Run these against a plain DuckDB session with spatial and httpfs loaded.
-- Each query reads remote GeoParquet on S3 and prunes on the bbox struct
-- before touching geometry, which is what keeps it to seconds rather than
-- hours.
--
-- Pin the release. 'latest' is not reproducible and the schema does change.

SET VARIABLE release = '2025-08-20.0';

-- ── Always count before you extract ────────────────────────────────────────

SELECT count(*) AS ghana_buildings
FROM read_parquet(
    's3://overturemaps-us-west-2/release/' || getvariable('release') ||
    '/theme=buildings/type=building/*',
    hive_partitioning = 1)
WHERE bbox.xmax >= -3.30 AND bbox.xmin <= 1.25
  AND bbox.ymax >=  4.50 AND bbox.ymin <= 11.20;

-- ── Places in Greater Accra, by category ───────────────────────────────────

SELECT categories.primary AS category, count(*) AS n
FROM read_parquet(
    's3://overturemaps-us-west-2/release/' || getvariable('release') ||
    '/theme=places/type=place/*',
    hive_partitioning = 1)
WHERE bbox.xmax >= -0.65 AND bbox.xmin <= 0.25
  AND bbox.ymax >=  5.45 AND bbox.ymin <= 5.95
  AND ST_Intersects(geometry, ST_MakeEnvelope(-0.65, 5.45, 0.25, 5.95))
GROUP BY 1
ORDER BY n DESC
LIMIT 40;

-- ── Ghana's boundary, straight from Overture divisions ─────────────────────
-- Useful as an exact clip geometry when no national boundary file is to hand.

SELECT id, names.primary AS name, subtype, class, geometry
FROM read_parquet(
    's3://overturemaps-us-west-2/release/' || getvariable('release') ||
    '/theme=divisions/type=division_area/*',
    hive_partitioning = 1)
WHERE country = 'GH'
  AND subtype = 'country';

-- ── Road length by class, in metres ────────────────────────────────────────
-- Note the transform. ST_Length on a 4326 geometry returns degrees, and
-- degrees are not a unit of distance. This is the most common silent error in
-- spatial SQL and it produces plausible-looking numbers, which is worse.

SELECT
    class,
    round(sum(ST_Length(ST_Transform(geometry, 'EPSG:4326', 'EPSG:32630'))) / 1000) AS km
FROM read_parquet(
    's3://overturemaps-us-west-2/release/' || getvariable('release') ||
    '/theme=transportation/type=segment/*',
    hive_partitioning = 1)
WHERE bbox.xmax >= -3.30 AND bbox.xmin <= 1.25
  AND bbox.ymax >=  4.50 AND bbox.ymin <= 11.20
  AND ST_Intersects(geometry, gh_bbox())
  AND subtype = 'road'
GROUP BY 1
ORDER BY km DESC;
