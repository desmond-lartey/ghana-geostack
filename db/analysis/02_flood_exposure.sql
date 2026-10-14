-- 02_flood_exposure.sql
-- Which buildings sit on land that has been under water before?
--
-- Accra floods most years. Kumasi and Tamale flood. This is the highest-value
-- question the stack can answer, and also the easiest one to answer
-- irresponsibly, so read the caveat before publishing anything from it.
--
-- CAVEAT, and it belongs on the map legend too:
--   This is OBSERVED historical surface water (JRC GSW) plus low-lying
--   terrain near a watercourse. It is not a hydraulic flood model. It has no
--   return period and no depth. It says "water has been here" and "this
--   ground is low and close to a river". Do not label the output "flood
--   risk", "1-in-100 year", or anything implying a modelled probability.
--
-- Run after 01. Depends on: core.building, core.waterway, core.dem.

\set ON_ERROR_STOP on
SET search_path TO analysis, core, public;

-- ── Step 1: low-lying land near watercourses ───────────────────────────────
-- 250 m of a river, and within 5 m elevation of the river bed. The elevation
-- test is what separates a floodplain from a hillside that happens to have a
-- stream at the bottom of it.

DROP TABLE IF EXISTS analysis.flood_prone_zone;
CREATE TABLE analysis.flood_prone_zone AS
WITH river AS (
    SELECT id, name, class, geom
    FROM core.waterway
    WHERE class IN ('river', 'stream')
      AND ST_Length(ST_Transform(geom, 32630)) > 500   -- drop map noise
),
corridor AS (
    SELECT
        r.id AS waterway_id,
        r.name,
        core.gh_buffer_m(r.geom, 250) AS geom,
        -- Elevation of the watercourse itself, sampled at its midpoint.
        (SELECT ST_Value(d.rast, ST_LineInterpolatePoint(r.geom, 0.5))
         FROM core.dem d
         WHERE ST_Intersects(d.rast, ST_LineInterpolatePoint(r.geom, 0.5))
         LIMIT 1) AS bed_elevation_m
    FROM river r
)
SELECT
    waterway_id,
    name,
    bed_elevation_m,
    geom,
    core.gh_area_m2(geom) / 1e6 AS area_km2
FROM corridor
WHERE bed_elevation_m IS NOT NULL;

CREATE INDEX flood_prone_zone_geom_idx ON analysis.flood_prone_zone USING GIST (geom);

-- ── Step 2: exposed buildings ──────────────────────────────────────────────
-- && gates on the bounding box using the index, ST_Intersects then does the
-- exact test. Both are needed: && alone over-selects by the corner of every
-- envelope, ST_Intersects alone scans everything.

DROP TABLE IF EXISTS analysis.building_flood_exposure;
CREATE TABLE analysis.building_flood_exposure AS
SELECT DISTINCT ON (b.id, b.region_id)
    b.id,
    b.region_id,
    b.district_id,
    b.geom,
    b.area_m2,
    z.waterway_id,
    z.name                                AS waterway_name,
    z.bed_elevation_m,
    -- Ground height of the building itself.
    (SELECT ST_Value(d.rast, ST_Centroid(b.geom))
     FROM core.dem d
     WHERE ST_Intersects(d.rast, ST_Centroid(b.geom))
     LIMIT 1)                             AS ground_elevation_m,
    core.gh_distance_m(b.geom, ST_Centroid(z.geom)) AS dist_to_water_m
FROM core.building b
JOIN analysis.flood_prone_zone z
  ON b.geom && z.geom
 AND ST_Intersects(b.geom, z.geom)
ORDER BY b.id, b.region_id, core.gh_distance_m(b.geom, ST_Centroid(z.geom));

-- Height above the nearest watercourse. Below 5 m is the exposure band.
ALTER TABLE analysis.building_flood_exposure
    ADD COLUMN height_above_water_m double precision
    GENERATED ALWAYS AS (ground_elevation_m - bed_elevation_m) STORED;

CREATE INDEX bfe_geom_idx ON analysis.building_flood_exposure USING GIST (geom);
CREATE INDEX bfe_district_idx ON analysis.building_flood_exposure (district_id);

-- ── Step 3: district rollup ────────────────────────────────────────────────

DROP TABLE IF EXISTS analysis.district_flood_summary;
CREATE TABLE analysis.district_flood_summary AS
SELECT
    d.id                                            AS district_id,
    d.name                                          AS district_name,
    d.region_id,
    d.geom,
    count(e.id)                                     AS exposed_buildings,
    count(e.id) FILTER (WHERE e.height_above_water_m < 2)  AS exposed_under_2m,
    count(e.id) FILTER (WHERE e.height_above_water_m < 5)  AS exposed_under_5m,
    round((sum(e.area_m2) / 1e4)::numeric, 1)       AS exposed_footprint_ha,
    -- Share of the district's buildings that are exposed. This is the number
    -- worth comparing across districts; raw counts just track district size.
    round(count(e.id)::numeric * 100
          / nullif((SELECT count(*) FROM core.building b
                    WHERE b.district_id = d.id), 0), 2) AS pct_exposed
FROM core.admin_district d
LEFT JOIN analysis.building_flood_exposure e ON e.district_id = d.id
GROUP BY d.id, d.name, d.region_id, d.geom;

CREATE INDEX dfs_geom_idx ON analysis.district_flood_summary USING GIST (geom);

-- ── Validation ─────────────────────────────────────────────────────────────

SELECT 'flood-prone zones'          AS check, count(*)::text AS value FROM analysis.flood_prone_zone
UNION ALL
SELECT 'zone area (km2)',  round(sum(area_km2)::numeric, 1)::text FROM analysis.flood_prone_zone
UNION ALL
SELECT 'exposed buildings',         count(*)::text FROM analysis.building_flood_exposure
UNION ALL
SELECT 'exposed, under 2m above water',
       count(*)::text FROM analysis.building_flood_exposure WHERE height_above_water_m < 2
UNION ALL
SELECT 'null elevation (raster gap)',
       count(*)::text FROM analysis.building_flood_exposure WHERE ground_elevation_m IS NULL
UNION ALL
SELECT 'negative height above water',
       count(*)::text FROM analysis.building_flood_exposure WHERE height_above_water_m < 0;

-- Reading the output:
--   Total zone area far above ~15,000 km2 means the buffer is catching every
--   drainage ditch in OSM. Tighten the length filter.
--   A large count of negative heights means the DEM and the waterway
--   geometry disagree - usually a bridge or a culvert mapped as a river, or
--   a DEM void. Investigate before publishing.
