-- transform/admin.sql — raw.admin_level_* into core.admin_*
--
-- This is where source-specific mess is cleaned up once, so that no query
-- downstream ever has to know whether the boundaries came from GADM, GRID3 or
-- the Ghana Statistical Service.
--
-- Region codes follow ISO 3166-2:GH where one exists. They are assigned here
-- by name rather than taken from the source, because source ids change
-- between releases and everything downstream keys on region_id.

\set ON_ERROR_STOP on
SET search_path TO core, raw, public;

BEGIN;

-- ── Country ────────────────────────────────────────────────────────────────

TRUNCATE core.admin_country CASCADE;

INSERT INTO core.admin_country (id, name, geom, source_id)
SELECT 'GHA',
       'Ghana',
       ST_Multi(core.gh_clean(ST_Union(geometry)))::geometry(MultiPolygon, 4326),
       'admin_gadm'
FROM raw.admin_level_0;

-- ── Regions ────────────────────────────────────────────────────────────────
-- The lookup is matched on the normalised name, so 'Ashanti', 'ASHANTI' and
-- 'Ashanti Region' all resolve. Any region that fails to match keeps a
-- generated code and is flagged by QC rather than silently dropped.

CREATE TEMP TABLE region_code (name_norm text PRIMARY KEY, code text, capital text) ON COMMIT DROP;

INSERT INTO region_code VALUES
    ('ahafo',         'GH-AF', 'Goaso'),
    ('ashanti',       'GH-AH', 'Kumasi'),
    ('bono',          'GH-BO', 'Sunyani'),
    ('bono east',     'GH-BE', 'Techiman'),
    ('central',       'GH-CP', 'Cape Coast'),
    ('eastern',       'GH-EP', 'Koforidua'),
    ('greater accra', 'GH-AA', 'Accra'),
    ('north east',    'GH-NE', 'Nalerigu'),
    ('northern',      'GH-NP', 'Tamale'),
    ('oti',           'GH-OT', 'Dambai'),
    ('savannah',      'GH-SV', 'Damongo'),
    ('upper east',    'GH-UE', 'Bolgatanga'),
    ('upper west',    'GH-UW', 'Wa'),
    ('volta',         'GH-TV', 'Ho'),
    ('western',       'GH-WP', 'Sekondi-Takoradi'),
    ('western north', 'GH-WN', 'Sefwi Wiawso');

TRUNCATE core.admin_region CASCADE;

INSERT INTO core.admin_region (id, name, capital, country_id, geom, source_id)
SELECT
    coalesce(rc.code, 'GH-X' || row_number() OVER (ORDER BY r.name_1)),
    r.name_1,
    rc.capital,
    'GHA',
    ST_Multi(core.gh_clean(r.geometry))::geometry(MultiPolygon, 4326),
    'admin_gadm'
FROM raw.admin_level_1 r
LEFT JOIN region_code rc
       ON rc.name_norm = core.gh_normalise_name(r.name_1);

-- ── Districts ──────────────────────────────────────────────────────────────
-- Assembly type comes from GADM's ENGTYPE_2 where present. The distinction
-- between metropolitan, municipal and district assemblies carries real
-- administrative weight in Ghana, so it is worth preserving rather than
-- flattening to "district".

TRUNCATE core.admin_district CASCADE;

INSERT INTO core.admin_district (id, name, region_id, assembly_type, geom, source_id)
SELECT
    d.gid_2,
    d.name_2,
    reg.id,
    CASE
        WHEN d.engtype_2 ILIKE '%metropol%' THEN 'metropolitan'
        WHEN d.engtype_2 ILIKE '%municipal%' THEN 'municipal'
        ELSE 'district'
    END,
    ST_Multi(core.gh_clean(d.geometry))::geometry(MultiPolygon, 4326),
    'admin_gadm'
FROM raw.admin_level_2 d
JOIN core.admin_region reg
  ON reg.name_norm = core.gh_normalise_name(d.name_1);

COMMIT;

-- ── Immediate feedback ─────────────────────────────────────────────────────

SELECT 'regions loaded' AS check, count(*)::text AS value FROM core.admin_region
UNION ALL
SELECT 'regions with a generated code (name did not match)',
       count(*)::text FROM core.admin_region WHERE id LIKE 'GH-X%'
UNION ALL
SELECT 'districts loaded', count(*)::text FROM core.admin_district
UNION ALL
SELECT 'districts with no region', count(*)::text
       FROM core.admin_district WHERE region_id IS NULL
UNION ALL
SELECT 'total area (km2)', round(sum(area_km2))::text FROM core.admin_region;

-- Regions carrying a GH-X code mean the source spells a region differently
-- from the lookup above. Add the spelling to region_code rather than renaming
-- the source data.
