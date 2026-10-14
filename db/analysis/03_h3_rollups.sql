-- 03_h3_rollups.sql
-- Hex-grid summaries. Choropleths by district mislead badly in Ghana because
-- districts differ in area by two orders of magnitude - a sparse northern
-- district and a dense Accra sub-metro get the same visual weight. Equal-area
-- hexes fix that.
--
-- Resolutions (from config/ghana.yml):
--   5  ~252 km2   national view
--   7  ~5.2 km2   regional patterns
--   9  ~0.10 km2  urban texture
--
-- Requires the h3-pg extension. If it is not installed, run the equivalent
-- in DuckDB instead - see duckdb/h3_rollups.sql, which produces the same
-- columns so downstream maps do not care which engine built them.

\set ON_ERROR_STOP on
SET search_path TO h3, analysis, core, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'h3') THEN
        RAISE EXCEPTION
          'h3 extension not installed. Either install h3-pg or run '
          'duckdb/h3_rollups.sql, which produces the same tables.';
    END IF;
END
$$;

-- ── Building density ───────────────────────────────────────────────────────

DROP TABLE IF EXISTS h3.building_density_r7;
CREATE TABLE h3.building_density_r7 AS
SELECT
    h3_lat_lng_to_cell(ST_Centroid(b.geom)::point, 7)::text AS h3,
    count(*)                                   AS building_count,
    round(sum(b.area_m2)::numeric)             AS total_footprint_m2,
    round(avg(b.area_m2)::numeric, 1)          AS mean_footprint_m2,
    -- Footprint as a share of the hex. A crude but effective built-up ratio.
    round((sum(b.area_m2) / 5161293.0 * 100)::numeric, 2) AS built_pct,
    mode() WITHIN GROUP (ORDER BY b.region_id) AS region_id
FROM core.building b
GROUP BY 1;

ALTER TABLE h3.building_density_r7 ADD PRIMARY KEY (h3);

-- Geometry is added as a separate column so the table stays small for
-- aggregation and only pays for boundary geometry once.
ALTER TABLE h3.building_density_r7 ADD COLUMN geom geometry(Polygon, 4326);
UPDATE h3.building_density_r7
   SET geom = ST_SetSRID(h3_cell_to_boundary_geometry(h3::h3index), 4326);
CREATE INDEX bd_r7_geom_idx ON h3.building_density_r7 USING GIST (geom);

-- ── Population ─────────────────────────────────────────────────────────────

DROP TABLE IF EXISTS h3.population_r7;
CREATE TABLE h3.population_r7 AS
SELECT
    h3_lat_lng_to_cell(ST_Centroid(p.geom)::point, 7)::text AS h3,
    p.year,
    round(sum(p.population)::numeric, 1)      AS population,
    round((sum(p.population) / 5.161293)::numeric, 1) AS people_per_km2
FROM core.population_grid p
GROUP BY 1, 2;

ALTER TABLE h3.population_r7 ADD PRIMARY KEY (h3, year);

-- ── Access, aggregated ─────────────────────────────────────────────────────
-- The single most useful national layer: how far is the typical building in
-- this hex from health care.

DROP TABLE IF EXISTS h3.access_r7;
CREATE TABLE h3.access_r7 AS
SELECT
    h3_lat_lng_to_cell(ST_Centroid(a.geom)::point, 7)::text AS h3,
    count(*)                                          AS buildings,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY a.health_dist_m)::numeric)
                                                      AS median_health_dist_m,
    round((count(*) FILTER (WHERE a.health_dist_m <= 5000))::numeric * 100
          / nullif(count(*), 0), 1)                   AS pct_within_5km
FROM analysis.building_access a
GROUP BY 1;

ALTER TABLE h3.access_r7 ADD PRIMARY KEY (h3);

-- ── National overview at r5 ────────────────────────────────────────────────

DROP TABLE IF EXISTS h3.national_r5;
CREATE TABLE h3.national_r5 AS
SELECT
    h3_cell_to_parent(b.h3::h3index, 5)::text AS h3,
    sum(b.building_count)                     AS building_count,
    round(sum(b.total_footprint_m2)::numeric) AS total_footprint_m2,
    round(avg(a.median_health_dist_m)::numeric) AS mean_median_health_dist_m
FROM h3.building_density_r7 b
LEFT JOIN h3.access_r7 a USING (h3)
GROUP BY 1;

ALTER TABLE h3.national_r5 ADD PRIMARY KEY (h3);
ALTER TABLE h3.national_r5 ADD COLUMN geom geometry(Polygon, 4326);
UPDATE h3.national_r5
   SET geom = ST_SetSRID(h3_cell_to_boundary_geometry(h3::h3index), 4326);
CREATE INDEX national_r5_geom_idx ON h3.national_r5 USING GIST (geom);

-- ── Validation ─────────────────────────────────────────────────────────────

SELECT 'r7 cells with buildings'  AS check, count(*)::text AS value FROM h3.building_density_r7
UNION ALL
SELECT 'r5 cells',                count(*)::text FROM h3.national_r5
UNION ALL
SELECT 'total buildings via h3',  sum(building_count)::text FROM h3.building_density_r7
UNION ALL
SELECT 'total buildings in core', count(*)::text FROM core.building
UNION ALL
SELECT 'built_pct over 100 (bug)', count(*)::text FROM h3.building_density_r7 WHERE built_pct > 100;

-- The two building totals must match exactly. If they do not, centroids are
-- falling outside the country envelope, or a partition was missed.
-- Ghana is ~238,500 km2, so expect roughly 950 r5 cells covering the country
-- and far fewer with buildings in them.
