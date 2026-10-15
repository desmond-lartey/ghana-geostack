-- 05_population.sql
-- Population, and everything that follows from knowing where people are.
--
-- Depends on core.admin_district.population, which is written by:
--
--   python pipelines/04_fetch_gee.py worldpop_population
--   python pipelines/05_zonal_stats.py data/raw/worldpop_population_ghana.tif \
--       --zones district --stat sum --column population --load
--
-- WHAT THIS IS, AND WHAT IT IS NOT
--
--   WorldPop is modelled, not counted. Census totals are distributed across a
--   grid using settlement pattern, land cover and roads. A district total is
--   therefore close to the census figure it was built from, and a single cell
--   is an estimate of how many people the model puts there.
--
--   That distinction survives aggregation badly. Summed to a district, these
--   numbers are defensible. Read off one 100 m cell, they are not a headcount
--   and must never be presented as one.
--
--   Where the Ghana Statistical Service publishes a figure for the same unit,
--   the GSS figure wins. This is what to use where they have not.

\set ON_ERROR_STOP on
SET search_path TO analysis, core, public;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM core.admin_district WHERE population IS NOT NULL
    ) THEN
        RAISE EXCEPTION
          'No population loaded. Run:  python pipelines/04_fetch_gee.py worldpop_population  '
          'then pipelines/05_zonal_stats.py with --column population --load';
    END IF;
END
$$;

-- ── 1. Density, and the districts that carry the country ───────────────────
-- Population alone ranks districts by how big they are. Density is what says
-- something about the place.

DROP TABLE IF EXISTS analysis.population_district;
CREATE TABLE analysis.population_district AS
SELECT
    d.id                                        AS district_id,
    d.name                                      AS district_name,
    d.region_id,
    r.name                                      AS region_name,
    d.assembly_type,
    round(d.population)                         AS population,
    round(d.area_km2::numeric, 1)               AS area_km2,
    round((d.population / nullif(d.area_km2, 0))::numeric, 1)
                                                AS people_per_km2,

    -- Share of the national total, which is the number that belongs in a
    -- sentence: "this district holds 4% of Ghana's people".
    round((d.population * 100.0
           / nullif(sum(d.population) OVER (), 0))::numeric, 2)
                                                AS pct_of_national,

    -- Rank within the region as well as nationally: a district can be crowded
    -- for the Northern Region and empty by Accra's standards, and both are
    -- worth knowing.
    rank() OVER (ORDER BY d.population DESC)    AS rank_national,
    rank() OVER (PARTITION BY d.region_id
                 ORDER BY d.population DESC)    AS rank_in_region,

    d.geom
FROM core.admin_district d
JOIN core.admin_region r ON r.id = d.region_id
WHERE d.population IS NOT NULL;

CREATE INDEX population_district_geom_idx ON analysis.population_district USING GIST (geom);
CREATE INDEX population_district_density_idx ON analysis.population_district (people_per_km2 DESC);

-- ── 2. Regional totals ─────────────────────────────────────────────────────

DROP TABLE IF EXISTS analysis.population_region;
CREATE TABLE analysis.population_region AS
SELECT
    r.id                                        AS region_id,
    r.name                                      AS region_name,
    r.capital,
    count(d.id)                                 AS districts,
    round(sum(d.population))                    AS population,
    round(r.area_km2::numeric, 1)               AS area_km2,
    round((sum(d.population) / nullif(r.area_km2, 0))::numeric, 1)
                                                AS people_per_km2,
    round((sum(d.population) * 100.0
           / nullif(sum(sum(d.population)) OVER (), 0))::numeric, 2)
                                                AS pct_of_national,

    -- How unevenly the region's people are spread across its own districts.
    -- A high ratio means one district dominates, which changes what a regional
    -- average is worth.
    round((max(d.population) / nullif(avg(d.population), 0))::numeric, 2)
                                                AS concentration_ratio,
    r.geom
FROM core.admin_region r
JOIN core.admin_district d ON d.region_id = r.id
WHERE d.population IS NOT NULL
GROUP BY r.id, r.name, r.capital, r.area_km2, r.geom;

CREATE INDEX population_region_geom_idx ON analysis.population_region USING GIST (geom);

-- ── 3. Population-weighted access ──────────────────────────────────────────
-- The share of BUILDINGS within 5 km of a clinic answers a question about
-- buildings. The share of PEOPLE answers the question anyone actually asked.
--
-- Buildings are used as the weight inside a district, because that is the
-- finest thing available: a district's population is apportioned across its
-- buildings, and each building carries its share. That assumes people are
-- spread evenly across buildings, which is wrong in detail — a compound
-- housing twelve holds more than a shop housing none — and right enough at
-- district scale to be worth doing.

DO $$
BEGIN
    IF to_regclass('analysis.building_access') IS NULL THEN
        RAISE NOTICE 'Skipping population-weighted access: run 01_accessibility.sql first';
        RETURN;
    END IF;

    EXECUTE $q$
        DROP TABLE IF EXISTS analysis.population_access;
        CREATE TABLE analysis.population_access AS
        WITH per_district AS (
            SELECT
                a.district_id,
                count(*)                                                AS buildings,
                count(*) FILTER (WHERE a.health_dist_m <= 5000)          AS within_5km,
                count(*) FILTER (WHERE a.health_dist_m <= 2000)          AS within_2km,
                count(*) FILTER (WHERE a.health_dist_m >  10000)         AS beyond_10km
            FROM analysis.building_access a
            WHERE a.district_id IS NOT NULL
            GROUP BY a.district_id
        )
        SELECT
            p.district_id,
            p.district_name,
            p.region_name,
            p.population,
            b.buildings,

            -- Population apportioned by building share.
            round(p.population * b.within_5km  / nullif(b.buildings, 0))  AS people_within_5km,
            round(p.population * b.within_2km  / nullif(b.buildings, 0))  AS people_within_2km,
            round(p.population * b.beyond_10km / nullif(b.buildings, 0))  AS people_beyond_10km,

            round((b.within_5km * 100.0 / nullif(b.buildings, 0))::numeric, 1)
                                                                          AS pct_within_5km,
            p.geom
        FROM analysis.population_district p
        JOIN per_district b ON b.district_id = p.district_id
    $q$;

    EXECUTE 'CREATE INDEX population_access_geom_idx ON analysis.population_access USING GIST (geom)';
END
$$;

-- ── 4. Population exposed to flood-prone ground ────────────────────────────
-- Same apportionment, applied to the exposure layer. This is the number that
-- makes a flood map actionable: not how much land is low, but how many people
-- live on it.

DO $$
BEGIN
    IF to_regclass('analysis.building_flood_exposure') IS NULL THEN
        RAISE NOTICE 'Skipping flood exposure: run 02_flood_exposure.sql first';
        RETURN;
    END IF;

    EXECUTE $q$
        DROP TABLE IF EXISTS analysis.population_flood_exposure;
        CREATE TABLE analysis.population_flood_exposure AS
        WITH exposed AS (
            SELECT district_id,
                   count(*)                                            AS exposed_buildings,
                   count(*) FILTER (WHERE height_above_water_m < 2)     AS exposed_under_2m
            FROM analysis.building_flood_exposure
            WHERE district_id IS NOT NULL
            GROUP BY district_id
        ),
        totals AS (
            SELECT district_id, count(*) AS buildings
            FROM core.building
            WHERE district_id IS NOT NULL
            GROUP BY district_id
        )
        SELECT
            p.district_id,
            p.district_name,
            p.region_name,
            p.population,
            coalesce(e.exposed_buildings, 0)                            AS exposed_buildings,
            round(p.population * coalesce(e.exposed_buildings, 0)
                  / nullif(t.buildings, 0))                             AS people_exposed,
            round(p.population * coalesce(e.exposed_under_2m, 0)
                  / nullif(t.buildings, 0))                             AS people_under_2m,
            round((coalesce(e.exposed_buildings, 0) * 100.0
                   / nullif(t.buildings, 0))::numeric, 2)               AS pct_exposed,
            p.geom
        FROM analysis.population_district p
        JOIN totals t  ON t.district_id = p.district_id
        LEFT JOIN exposed e ON e.district_id = p.district_id
    $q$;

    EXECUTE 'CREATE INDEX population_flood_geom_idx ON analysis.population_flood_exposure USING GIST (geom)';
END
$$;

-- ── 5. Heat exposure, when land surface temperature has been loaded ────────
-- The urban heat pattern: temperature per district, the excess over the
-- regional norm, and how many people live in the hot districts.
--
-- Load the input with:
--   python pipelines/04_fetch_gee.py landsat_lst --start 2024-11-01 --end 2025-03-31
--   python pipelines/05_zonal_stats.py data/raw/landsat_lst_ghana.tif \
--       --zones district --stat mean --column lst_c \
--       --scale 0.00341802 --offset -124.15 --load

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core' AND table_name = 'admin_district'
          AND column_name = 'lst_c'
    ) THEN
        RAISE NOTICE 'Skipping heat exposure: no lst_c column. See the header of this section.';
        RETURN;
    END IF;

    EXECUTE $q$
        DROP TABLE IF EXISTS analysis.population_heat;
        CREATE TABLE analysis.population_heat AS
        WITH regional AS (
            SELECT region_id, avg(lst_c) AS region_mean_c
            FROM core.admin_district
            WHERE lst_c IS NOT NULL
            GROUP BY region_id
        )
        SELECT
            p.district_id,
            p.district_name,
            p.region_name,
            p.population,
            round(d.lst_c::numeric, 1)                          AS lst_c,
            round(g.region_mean_c::numeric, 1)                  AS region_mean_c,

            -- Heat island intensity: how much hotter this district runs than
            -- the region around it. The comparison is regional rather than
            -- national because Ghana's north is hotter than its south for
            -- reasons that have nothing to do with urban form.
            round((d.lst_c - g.region_mean_c)::numeric, 1)      AS excess_c,

            p.people_per_km2,
            p.geom
        FROM analysis.population_district p
        JOIN core.admin_district d ON d.id = p.district_id
        JOIN regional g ON g.region_id = p.region_id
        WHERE d.lst_c IS NOT NULL
    $q$;

    EXECUTE 'CREATE INDEX population_heat_geom_idx ON analysis.population_heat USING GIST (geom)';
END
$$;

-- ── Validation ─────────────────────────────────────────────────────────────

SELECT 'districts with population'  AS check, count(*)::text AS value
       FROM analysis.population_district
UNION ALL
SELECT 'national total',
       to_char(sum(population), 'FM999,999,999') FROM analysis.population_district
UNION ALL
SELECT 'regions',                   count(*)::text FROM analysis.population_region
UNION ALL
SELECT 'densest district (per km2)',
       to_char(max(people_per_km2), 'FM999,999') FROM analysis.population_district
UNION ALL
SELECT 'sparsest district (per km2)',
       to_char(min(people_per_km2), 'FM999,999') FROM analysis.population_district;

-- Reading the output:
--
--   The national total should land near 30.8 million, the 2021 census figure.
--   Materially above 34 million or below 28 million means the raster was
--   summed wrong — usually a scale factor, or a raster fetched for one city
--   and summed as though it were national.
--
--   Ghana's densest districts are Accra sub-metros, well past 10,000 people
--   per km2. The sparsest are in Savannah and North East, in the low tens. A
--   maximum under 1,000 means the zonal sum lost most of its pixels.

SELECT region_name, districts,
       to_char(population, 'FM999,999,999') AS population,
       people_per_km2, pct_of_national
FROM analysis.population_region
ORDER BY population DESC;
