-- checks.sql
-- Every check writes a row into meta.qc_result, so a run leaves a record
-- rather than a scrollback buffer. Severity 'error' fails the build.
--
-- The rule this enforces: a map is not publishable until the SQL underneath
-- it has been checked. Not eyeballed - checked, with a number and an
-- expectation next to it.
--
-- Run: make qc

\set ON_ERROR_STOP on
SET search_path TO meta, core, analysis, public;

-- Open a run and remember its id for the rest of the file.
INSERT INTO meta.qc_run (git_sha, note)
VALUES (current_setting('ghana.git_sha', true), 'checks.sql')
RETURNING id \gset qc_run_

\set RUN :qc_run_id

-- psql variables are not visible inside a DO block, so the run id is also
-- published as a session setting that plpgsql can read.
SELECT set_config('ghana.qc_run', :'RUN', false);

-- ─────────────────────────────────────────────────────────────────────────
-- 1. CRS consistency. One wrong SRID and every join silently returns zero.
-- ─────────────────────────────────────────────────────────────────────────

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT
    :RUN,
    'srid_is_4326',
    f_table_schema || '.' || f_table_name || '.' || f_geometry_column,
    'error',
    srid = 4326,
    srid,
    '4326',
    CASE WHEN srid = 4326 THEN NULL
         ELSE 'Stored geometry must be EPSG:4326. Transform on read, not on store.' END
FROM geometry_columns
WHERE f_table_schema IN ('core','analysis','h3','serve');

-- Rasters too.
INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT
    :RUN,
    'raster_srid_is_4326',
    r_table_schema || '.' || r_table_name,
    'warning',
    srid = 4326,
    srid,
    '4326',
    'Rasters may legitimately be stored in 32630 for analysis speed. Confirm intent.'
FROM raster_columns
WHERE r_table_schema IN ('core','analysis');

-- ─────────────────────────────────────────────────────────────────────────
-- 2. Geometry validity and emptiness.
-- ─────────────────────────────────────────────────────────────────────────

DO $qc$
DECLARE
    t record;
    bad bigint;
    empt bigint;
    total bigint;
BEGIN
    FOR t IN
        SELECT f_table_schema AS s, f_table_name AS tb, f_geometry_column AS g
        FROM geometry_columns
        WHERE f_table_schema IN ('core','analysis','h3')
    LOOP
        EXECUTE format('SELECT count(*) FROM %I.%I', t.s, t.tb) INTO total;
        CONTINUE WHEN total = 0;

        EXECUTE format('SELECT count(*) FROM %I.%I WHERE NOT ST_IsValid(%I)',
                       t.s, t.tb, t.g) INTO bad;
        EXECUTE format('SELECT count(*) FROM %I.%I WHERE ST_IsEmpty(%I) OR %I IS NULL',
                       t.s, t.tb, t.g, t.g) INTO empt;

        INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
        VALUES
          (current_setting('ghana.qc_run')::bigint, 'geometry_valid',
           t.s || '.' || t.tb, 'error', bad = 0, bad, '0',
           CASE WHEN bad > 0 THEN 'Run core.gh_clean() on load.' END),
          (current_setting('ghana.qc_run')::bigint, 'geometry_not_empty',
           t.s || '.' || t.tb, 'error', empt = 0, empt, '0', NULL);
    END LOOP;
END
$qc$;

-- ─────────────────────────────────────────────────────────────────────────
-- 3. Everything must fall inside Ghana. Catches the classic 0,0 null island
--    and lat/lon swaps, which put Ghana in the Indian Ocean.
-- ─────────────────────────────────────────────────────────────────────────

DO $qc$
DECLARE
    t record;
    outside bigint;
BEGIN
    FOR t IN
        SELECT f_table_schema AS s, f_table_name AS tb, f_geometry_column AS g
        FROM geometry_columns
        WHERE f_table_schema IN ('core','analysis','h3')
    LOOP
        EXECUTE format(
            'SELECT count(*) FROM %I.%I WHERE %I IS NOT NULL AND NOT (%I && core.gh_bbox())',
            t.s, t.tb, t.g, t.g) INTO outside;

        INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
        VALUES (current_setting('ghana.qc_run')::bigint, 'within_ghana_bbox',
                t.s || '.' || t.tb, 'error', outside = 0, outside, '0',
                CASE WHEN outside > 0 THEN
                  'Features outside the Ghana envelope. Usual causes: lon/lat '
                  'swapped, coordinates at 0,0, or a source CRS assumed rather '
                  'than read.' END);
    END LOOP;
END
$qc$;

-- ─────────────────────────────────────────────────────────────────────────
-- 4. Admin hierarchy integrity. Ghana-specific expectations.
-- ─────────────────────────────────────────────────────────────────────────

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'region_count', 'core.admin_region', 'error',
       count(*) = 16, count(*), '16',
       'Ghana has had 16 regions since the 2018-19 referendums. A count of 10 '
       'means a pre-2018 source got loaded.'
FROM core.admin_region;

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'district_count', 'core.admin_district', 'error',
       count(*) = 260, count(*), '260',
       'The COD-AB boundary set defines 260 MMDAs. A different count means a '
       'superseded boundary set, or the wrong admin level.'
FROM core.admin_district;

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'pcode_format', 'core.admin_district', 'error',
       count(*) = 0, count(*), '0',
       'District p-codes must match GHrrdd. P-codes are the join key across '
       'the database; a malformed one breaks the hierarchy silently.'
FROM core.admin_district WHERE id !~ '^GH[0-9]{4}$';

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'pcode_hierarchy', 'core.admin_district', 'error',
       count(*) = 0, count(*), '0',
       'Every district p-code must begin with its region p-code.'
FROM core.admin_district d
LEFT JOIN core.admin_region r ON r.id = left(d.id, 4)
WHERE r.id IS NULL;

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'districts_nest_in_regions', 'core.admin_district', 'error',
       count(*) = 0, count(*), '0',
       'Every district centroid must fall inside its declared region.'
FROM core.admin_district d
JOIN core.admin_region r ON r.id = d.region_id
WHERE NOT ST_Contains(r.geom, ST_PointOnSurface(d.geom));

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'country_area_km2', 'core.admin_country', 'warning',
       abs(sum(area_km2) - 239473) < 4000, round(sum(area_km2)), '239,473 km2 +/- 4,000',
       'The COD boundary set reports 239,473 km2, slightly above the commonly '
       'cited land area of 238,533 km2 because it includes coastal and inland '
       'water extent. A large deviation means simplified boundaries or a '
       'missing region.'
FROM core.admin_region;

-- ─────────────────────────────────────────────────────────────────────────
-- 5. Attribute completeness on the columns people actually use.
-- ─────────────────────────────────────────────────────────────────────────

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'buildings_have_region', 'core.building', 'error',
       count(*) = 0, count(*), '0',
       'Buildings in the default partition were not matched to a region.'
FROM core.building WHERE region_id IS NULL;

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'road_class_known', 'core.road', 'warning',
       count(*) = 0, count(*), '0',
       'Roads with no class cannot be styled or filtered.'
FROM core.road WHERE class IS NULL OR class = '';

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'facility_category_valid', 'core.facility', 'error',
       count(*) = 0, count(*), '0', NULL
FROM core.facility
WHERE category NOT IN ('health','education','market','water','energy','government','other');

-- ─────────────────────────────────────────────────────────────────────────
-- 6. Plausibility. Numbers that are structurally fine but factually absurd.
-- ─────────────────────────────────────────────────────────────────────────

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'building_footprint_plausible', 'core.building', 'warning',
       count(*) = 0, count(*), '0',
       'Footprints under 4 m2 or over 100,000 m2. Tiny ones are usually ML '
       'artefacts; huge ones are usually merged blocks or a dissolve gone wrong.'
FROM core.building WHERE area_m2 < 4 OR area_m2 > 100000;

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'building_height_plausible', 'core.building', 'warning',
       count(*) = 0, count(*), '0',
       'Heights above 120 m. Ghana''s tallest buildings are around 100 m, so '
       'anything higher is a units error - feet parsed as metres, most likely.'
FROM core.building WHERE height_m > 120;

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'elevation_plausible', 'core.dem', 'warning',
       count(*) = 0, count(*), '0',
       'Ghana runs from sea level to Mount Afadja at about 885 m. Values '
       'outside -10 to 1000 m indicate a nodata value being read as data.'
FROM (
    SELECT (ST_SummaryStats(rast)).*
    FROM core.dem
) s
WHERE s.min < -10 OR s.max > 1000;

-- ─────────────────────────────────────────────────────────────────────────
-- 7. Governance. No publishing without a licence and an attribution string.
-- ─────────────────────────────────────────────────────────────────────────

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'registered_in_metadata', 'meta.dataset', 'error',
       count(*) = 0, count(*), '0',
       'Tables in core with no meta.dataset row. Register them in the loader.'
FROM (
    SELECT c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'core' AND c.relkind IN ('r','p')
      AND NOT EXISTS (SELECT 1 FROM meta.dataset d
                      WHERE d.schema_name = 'core' AND d.table_name = c.relname)
) missing;

INSERT INTO meta.qc_result (run_id, check_name, target, severity, passed, observed, expected, detail)
SELECT :RUN, 'publishable_has_attribution', 'meta.dataset', 'error',
       count(*) = 0, count(*), '0',
       'A dataset marked publishable with no attribution string breaches '
       'ODbL and CC-BY. Fix before any tile is served.'
FROM meta.dataset
WHERE publishable AND (attribution IS NULL OR attribution = '');

-- ─────────────────────────────────────────────────────────────────────────
-- Close the run.
-- ─────────────────────────────────────────────────────────────────────────

UPDATE meta.qc_run
SET finished_at = now(),
    passed = NOT EXISTS (
        SELECT 1 FROM meta.qc_result
        WHERE run_id = :RUN AND NOT passed AND severity = 'error')
WHERE id = :RUN;

-- Report.
SELECT severity,
       count(*)                            AS checks,
       count(*) FILTER (WHERE NOT passed)  AS failed
FROM meta.qc_result WHERE run_id = :RUN
GROUP BY severity ORDER BY severity;

SELECT check_name, target, observed, expected, detail
FROM meta.qc_result
WHERE run_id = :RUN AND NOT passed
ORDER BY severity, check_name;
