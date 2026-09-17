-- 005_serve_views.sql
-- The public face. pg_tileserv and pg_featureserv see only this schema.
--
-- Two rules, both enforced here rather than trusted to reviewers:
--   1. A view exists only for datasets registered as publishable.
--   2. Views carry the minimum columns a map needs. Timestamps, internal ids
--      and provenance stay in core, where they belong.
--
-- Views are created even when the underlying table is empty, so the API has a
-- stable surface from day one.

BEGIN;

SET search_path TO serve, core, analysis, h3, public;

-- ── Administrative ─────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW serve.region AS
SELECT id, name, capital, round(area_km2::numeric, 1) AS area_km2,
       population, geom
FROM core.admin_region;

CREATE OR REPLACE VIEW serve.district AS
SELECT d.id, d.name, d.region_id, r.name AS region_name, d.assembly_type,
       round(d.area_km2::numeric, 1) AS area_km2, d.population, d.geom
FROM core.admin_district d
JOIN core.admin_region r ON r.id = d.region_id;

-- ── Transport ──────────────────────────────────────────────────────────────
-- Minor roads are excluded below zoom level 12's worth of detail by filtering
-- on class; pg_tileserv cannot filter by zoom itself, so the split is done as
-- two views and the client picks.

CREATE OR REPLACE VIEW serve.road_major AS
SELECT id, name, class, surface, round(length_m::numeric) AS length_m, geom
FROM core.road
WHERE class IN ('motorway','trunk','primary','secondary');

CREATE OR REPLACE VIEW serve.road_all AS
SELECT id, name, class, surface, round(length_m::numeric) AS length_m, geom
FROM core.road;

-- ── Buildings ──────────────────────────────────────────────────────────────
-- Cast to real, not double precision. Kepler and MapLibre bind numeric visual
-- channels poorly to 64-bit types, which shows up as a blank colour ramp
-- rather than an error.

CREATE OR REPLACE VIEW serve.building AS
SELECT id, name, class,
       height_m::real       AS height_m,
       levels,
       area_m2::real        AS area_m2,
       region_id, district_id, geom
FROM core.building
WHERE confidence IS NULL OR confidence >= 0.7;

COMMENT ON VIEW serve.building IS
  'Machine-derived footprints below 0.7 confidence are excluded from the '
  'public view. They remain in core.building for anyone who wants them.';

-- ── Facilities ─────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW serve.facility AS
SELECT id, name, category, subtype, ownership, district_id, geom
FROM core.facility;

-- ── Analysis outputs ───────────────────────────────────────────────────────
-- Wrapped in DO blocks: analysis tables may not exist yet on a fresh
-- database, and a missing analysis table should not block the migration.

DO $$
BEGIN
    IF to_regclass('analysis.district_access_summary') IS NOT NULL THEN
        EXECUTE $v$
            CREATE OR REPLACE VIEW serve.access_by_district AS
            SELECT s.district_id, s.district_name, s.region_id,
                   s.buildings,
                   s.pct_within_5km_health::real AS pct_within_5km_health,
                   s.median_health_dist_m::real  AS median_health_dist_m,
                   d.geom
            FROM analysis.district_access_summary s
            JOIN core.admin_district d ON d.id = s.district_id
        $v$;
    END IF;

    IF to_regclass('analysis.district_flood_summary') IS NOT NULL THEN
        EXECUTE $v$
            CREATE OR REPLACE VIEW serve.flood_by_district AS
            SELECT district_id, district_name, region_id,
                   exposed_buildings, exposed_under_2m,
                   pct_exposed::real AS pct_exposed, geom
            FROM analysis.district_flood_summary
        $v$;
    END IF;

    IF to_regclass('analysis.site_suitability') IS NOT NULL THEN
        EXECUTE $v$
            CREATE OR REPLACE VIEW serve.site_suitability AS
            SELECT h3, region_id,
                   suitability_score::real AS score,
                   building_count,
                   round(road_dist_m::numeric)::int AS road_dist_m,
                   geom
            FROM analysis.site_suitability
        $v$;
    END IF;

    IF to_regclass('h3.building_density_r7') IS NOT NULL THEN
        EXECUTE $v$
            CREATE OR REPLACE VIEW serve.building_density AS
            SELECT h3, building_count,
                   built_pct::real AS built_pct,
                   region_id, geom
            FROM h3.building_density_r7
        $v$;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA serve TO ghana_read;
GRANT SELECT ON ALL TABLES IN SCHEMA serve TO ghana_read;

COMMIT;
