-- 01_accessibility.sql
-- How far is a settlement from care and schooling?
--
-- This is the Denver pipeline's "distance to nearest road" idea pointed at a
-- question Ghana actually asks. Ghana Health Service plans around a 5 km
-- catchment for a CHPS compound, so 5 km is the band that matters, not an
-- arbitrary round number.
--
-- Run: make analysis  (or psql -f this file)

\set ON_ERROR_STOP on
SET search_path TO analysis, core, public;

-- ── Nearest facility per building ──────────────────────────────────────────
-- The <-> operator does an index-ordered nearest-neighbour scan. Without it
-- this is a cross join across millions of buildings and will not finish.

DROP TABLE IF EXISTS analysis.building_access;
CREATE TABLE analysis.building_access AS
SELECT
    b.id,
    b.region_id,
    b.district_id,
    b.geom,
    nearest_health.facility_id      AS nearest_health_id,
    nearest_health.name             AS nearest_health_name,
    nearest_health.dist_m           AS health_dist_m,
    nearest_school.facility_id      AS nearest_school_id,
    nearest_school.dist_m           AS school_dist_m
FROM core.building b
LEFT JOIN LATERAL (
    SELECT f.id AS facility_id,
           f.name,
           ST_Distance(ST_Transform(b.geom, 32630),
                       ST_Transform(f.geom, 32630)) AS dist_m
    FROM core.facility f
    WHERE f.category = 'health'
    ORDER BY b.geom <-> f.geom
    LIMIT 1
) nearest_health ON true
LEFT JOIN LATERAL (
    SELECT f.id AS facility_id,
           ST_Distance(ST_Transform(b.geom, 32630),
                       ST_Transform(f.geom, 32630)) AS dist_m
    FROM core.facility f
    WHERE f.category = 'education'
    ORDER BY b.geom <-> f.geom
    LIMIT 1
) nearest_school ON true;

CREATE INDEX building_access_geom_idx ON analysis.building_access USING GIST (geom);
CREATE INDEX building_access_health_idx ON analysis.building_access (health_dist_m);

-- NOTE on the <-> ordering above: it sorts by planar degree distance for
-- speed, then the exact metre distance is computed only for the winner. Over
-- a few kilometres at Ghana's latitudes the two rankings agree. If you need
-- a guaranteed-exact nearest neighbour, widen to the 5 nearest by <-> and
-- pick the minimum metre distance from those.

-- ── District summary: the number that goes on a slide ──────────────────────

DROP TABLE IF EXISTS analysis.district_access_summary;
CREATE TABLE analysis.district_access_summary AS
SELECT
    d.id                                                    AS district_id,
    d.name                                                  AS district_name,
    d.region_id,
    count(*)                                                AS buildings,
    round((count(*) FILTER (WHERE a.health_dist_m <= 5000))::numeric
          * 100 / nullif(count(*), 0), 1)                   AS pct_within_5km_health,
    round((count(*) FILTER (WHERE a.health_dist_m <= 2000))::numeric
          * 100 / nullif(count(*), 0), 1)                   AS pct_within_2km_health,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY a.health_dist_m)::numeric)
                                                            AS median_health_dist_m,
    round(max(a.health_dist_m)::numeric)                    AS max_health_dist_m,
    round((count(*) FILTER (WHERE a.school_dist_m <= 3000))::numeric
          * 100 / nullif(count(*), 0), 1)                   AS pct_within_3km_school
FROM analysis.building_access a
JOIN core.admin_district d ON d.id = a.district_id
GROUP BY d.id, d.name, d.region_id;

-- ── Underserved clusters: where a new CHPS compound would do most good ─────
-- Buildings more than 5 km from care, clustered so the result is a list of
-- places rather than a list of roofs.

DROP TABLE IF EXISTS analysis.underserved_cluster;
CREATE TABLE analysis.underserved_cluster AS
WITH far AS (
    SELECT id, region_id, district_id, geom, health_dist_m
    FROM analysis.building_access
    WHERE health_dist_m > 5000
),
clustered AS (
    SELECT *,
           ST_ClusterDBSCAN(ST_Transform(geom, 32630),
                            eps := 500, minpoints := 20) OVER () AS cluster_id
    FROM far
)
SELECT
    cluster_id,
    district_id,
    region_id,
    count(*)                                        AS building_count,
    round(avg(health_dist_m)::numeric)              AS avg_health_dist_m,
    ST_Centroid(ST_Collect(geom))                   AS centroid,
    ST_ConvexHull(ST_Collect(geom))                 AS extent
FROM clustered
WHERE cluster_id IS NOT NULL
GROUP BY cluster_id, district_id, region_id
HAVING count(*) >= 20
ORDER BY building_count DESC;

CREATE INDEX underserved_cluster_geom_idx ON analysis.underserved_cluster USING GIST (centroid);

-- ── Validation, in SQL, before anyone looks at a map ───────────────────────
-- Every figure below should be sane for Ghana. If it is not, stop and debug.

SELECT 'buildings scored'        AS check, count(*)::text AS value FROM analysis.building_access
UNION ALL
SELECT 'null health distance',   count(*)::text FROM analysis.building_access WHERE health_dist_m IS NULL
UNION ALL
SELECT 'median health dist (m)',
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY health_dist_m)::numeric)::text
       FROM analysis.building_access
UNION ALL
SELECT 'max health dist (km)',
       round((max(health_dist_m)/1000)::numeric, 1)::text FROM analysis.building_access
UNION ALL
SELECT 'underserved clusters',   count(*)::text FROM analysis.underserved_cluster
UNION ALL
SELECT 'districts summarised',   count(*)::text FROM analysis.district_access_summary;

-- Expect: districts summarised close to 261. A max distance above ~120 km
-- means facility coverage failed to load for part of the north, not that
-- someone lives 120 km from a clinic.
