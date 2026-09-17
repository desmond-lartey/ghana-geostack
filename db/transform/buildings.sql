-- transform/buildings.sql — raw.building into the partitioned core.building
--
-- Two jobs: attach every footprint to a region and a district (which decides
-- its partition), and parse the height field, which arrives as free text in
-- OSM and as a float in Overture.

\set ON_ERROR_STOP on
SET search_path TO core, raw, public;

BEGIN;

TRUNCATE core.building;

INSERT INTO core.building
    (source_ref, name, class, height_m, levels, confidence,
     district_id, region_id, geom, source_id)
SELECT
    b.id::text,
    nullif(b.name, ''),
    nullif(b.class, ''),

    -- Height: numeric in Overture, free text in OSM ('12', '12 m', '3 floors').
    -- Anything that is not a clean number becomes NULL rather than a guess.
    CASE
        WHEN b.height_m IS NOT NULL THEN b.height_m::double precision
        ELSE NULL
    END,
    b.levels::smallint,
    b.confidence::double precision,

    d.id,
    coalesce(r.name, 'Unassigned'),
    ST_Multi(core.gh_clean(b.geometry))::geometry(MultiPolygon, 4326),
    b.source_id
FROM raw.building b
-- Point-on-surface rather than centroid: a centroid can fall outside a
-- concave polygon and get assigned to the wrong district.
LEFT JOIN core.admin_district d
       ON ST_Contains(d.geom, ST_PointOnSurface(b.geometry))
LEFT JOIN core.admin_region r
       ON r.id = d.region_id
WHERE b.geometry IS NOT NULL
  AND ST_IsValid(core.gh_clean(b.geometry))
  AND b.geometry && core.gh_bbox();

COMMIT;

ANALYZE core.building;

SELECT 'buildings loaded'         AS check, count(*)::text AS value FROM core.building
UNION ALL
SELECT 'unassigned to a region',  count(*)::text FROM core.building_unassigned
UNION ALL
SELECT 'with a parsed height',    count(*)::text FROM core.building WHERE height_m IS NOT NULL
UNION ALL
SELECT 'median footprint (m2)',
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY area_m2)::numeric, 1)::text
       FROM core.building
UNION ALL
SELECT 'total footprint (km2)',
       round((sum(area_m2)/1e6)::numeric, 1)::text FROM core.building;

-- A large unassigned count usually means district boundaries are missing
-- offshore or along the northern border, not that the buildings are wrong.
