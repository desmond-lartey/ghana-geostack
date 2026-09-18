-- transform/admin.sql — raw COD boundaries into core.admin_*
--
-- Source: Ghana Common Operational Dataset, administrative boundaries
-- (COD-AB), valid from 2021-03-08, version v01.
--
-- P-codes are the join key. Every administrative unit carries one, they are
-- stable across releases, and they do not depend on spelling:
--
--   GH          country
--   GH01..GH16  regions
--   GHrrdd      districts, where rr identifies the parent region
--
-- Because the parent p-code is a prefix of the child p-code, the hierarchy is
-- derived by string match rather than by a spatial join. That is both exact
-- and fast, and it removes the class of error where a district is assigned to
-- the wrong region because its centroid fell outside a concave boundary.

\set ON_ERROR_STOP on
SET search_path TO core, raw, public;

BEGIN;

-- ── Name corrections ───────────────────────────────────────────────────────
-- The published dataset spells one region as "Northern East". The official
-- name is North East. The correction is applied here and the source spelling
-- is kept as a search alias, so a query using either form resolves.

CREATE TEMP TABLE name_fix (pcode text PRIMARY KEY, official text, alias text)
    ON COMMIT DROP;

INSERT INTO name_fix VALUES
    ('GH09', 'North East', 'Northern East');

-- ── Region capitals ────────────────────────────────────────────────────────

CREATE TEMP TABLE region_capital (pcode text PRIMARY KEY, capital text)
    ON COMMIT DROP;

INSERT INTO region_capital VALUES
    ('GH01', 'Goaso'),            ('GH02', 'Kumasi'),
    ('GH03', 'Sunyani'),          ('GH04', 'Techiman'),
    ('GH05', 'Cape Coast'),       ('GH06', 'Koforidua'),
    ('GH07', 'Accra'),            ('GH08', 'Tamale'),
    ('GH09', 'Nalerigu'),         ('GH10', 'Dambai'),
    ('GH11', 'Damongo'),          ('GH12', 'Bolgatanga'),
    ('GH13', 'Wa'),               ('GH14', 'Ho'),
    ('GH15', 'Sekondi-Takoradi'), ('GH16', 'Sefwi Wiawso');

-- ── Country ────────────────────────────────────────────────────────────────

TRUNCATE core.admin_country CASCADE;

INSERT INTO core.admin_country (id, name, geom, source_id)
SELECT 'GHA',
       coalesce(adm0_name, 'Ghana'),
       ST_Multi(core.gh_clean(geometry))::geometry(MultiPolygon, 4326),
       'cod_ab_ghana'
FROM raw.admin_level_0;

-- ── Regions ────────────────────────────────────────────────────────────────

TRUNCATE core.admin_region CASCADE;

INSERT INTO core.admin_region
    (id, name, capital, country_id, geom, source_id, vintage, valid_from, shape_id)
SELECT
    r.adm1_pcode,
    coalesce(f.official, r.adm1_name),
    c.capital,
    'GHA',
    ST_Multi(core.gh_clean(r.geometry))::geometry(MultiPolygon, 4326),
    'cod_ab_ghana',
    '2019-',
    to_date(nullif(r.valid_on, ''), 'YYYYMMDD'),
    r.adm1_pcode
FROM raw.admin_level_1 r
LEFT JOIN name_fix f       ON f.pcode = r.adm1_pcode
LEFT JOIN region_capital c ON c.pcode = r.adm1_pcode;

-- ── Districts ──────────────────────────────────────────────────────────────
-- Assembly type is derived from the district name, which is how the
-- distinction is published. The suffix is not applied to every unit, so this
-- is a sensible default rather than the legal classification; the authority
-- is the Local Governance Act instrument that created each assembly.

TRUNCATE core.admin_district CASCADE;

INSERT INTO core.admin_district
    (id, name, region_id, assembly_type, geom, source_id, vintage, valid_from, shape_id)
SELECT
    d.adm2_pcode,
    d.adm2_name,
    -- The region p-code is the first four characters of the district p-code.
    left(d.adm2_pcode, 4),
    CASE
        WHEN d.adm2_name ILIKE '%metropol%'  THEN 'metropolitan'
        WHEN d.adm2_name ILIKE '%municipal%' THEN 'municipal'
        ELSE 'district'
    END,
    ST_Multi(core.gh_clean(d.geometry))::geometry(MultiPolygon, 4326),
    'cod_ab_ghana',
    '2019-',
    to_date(nullif(d.valid_on, ''), 'YYYYMMDD'),
    d.adm2_pcode
FROM raw.admin_level_2 d;

-- ── Aliases ────────────────────────────────────────────────────────────────
-- Search resolves against this table as well as the primary name, so both the
-- official spelling and the published variant find the same unit.

CREATE TABLE IF NOT EXISTS core.admin_alias (
    id         bigserial PRIMARY KEY,
    pcode      text NOT NULL,
    level      text NOT NULL CHECK (level IN ('ADM0','ADM1','ADM2')),
    alias      text NOT NULL,
    alias_norm text GENERATED ALWAYS AS (core.gh_normalise_name(alias)) STORED,
    source     text,
    UNIQUE (pcode, alias)
);

CREATE INDEX IF NOT EXISTS admin_alias_norm_idx
    ON core.admin_alias USING GIN (alias_norm gin_trgm_ops);

INSERT INTO core.admin_alias (pcode, level, alias, source)
SELECT pcode, 'ADM1', alias, 'COD source spelling' FROM name_fix
ON CONFLICT (pcode, alias) DO NOTHING;

-- Pre-2019 region names, so data recorded under the old ten-region
-- configuration still resolves to a place.
INSERT INTO core.admin_alias (pcode, level, alias, source) VALUES
    ('GH01', 'ADM1', 'Brong Ahafo', 'pre-2019 predecessor'),
    ('GH03', 'ADM1', 'Brong Ahafo', 'pre-2019 predecessor'),
    ('GH04', 'ADM1', 'Brong Ahafo', 'pre-2019 predecessor')
ON CONFLICT (pcode, alias) DO NOTHING;

COMMIT;

ANALYZE core.admin_region;
ANALYZE core.admin_district;

-- ── Validation ─────────────────────────────────────────────────────────────

SELECT 'regions'                     AS check, count(*)::text AS value FROM core.admin_region
UNION ALL
SELECT 'districts',                  count(*)::text FROM core.admin_district
UNION ALL
SELECT 'districts with no region',   count(*)::text
       FROM core.admin_district d
       LEFT JOIN core.admin_region r ON r.id = d.region_id
       WHERE r.id IS NULL
UNION ALL
SELECT 'region p-codes malformed',   count(*)::text
       FROM core.admin_region WHERE id !~ '^GH[0-9]{2}$'
UNION ALL
SELECT 'district p-codes malformed', count(*)::text
       FROM core.admin_district WHERE id !~ '^GH[0-9]{4}$'
UNION ALL
SELECT 'total region area (km2)',    round(sum(area_km2))::text FROM core.admin_region
UNION ALL
SELECT 'total district area (km2)',  round(sum(area_km2))::text FROM core.admin_district
UNION ALL
SELECT 'metropolitan assemblies',    count(*)::text
       FROM core.admin_district WHERE assembly_type = 'metropolitan';

-- Districts per region: the quickest way to spot a level loaded against the
-- wrong parent.
SELECT r.id, r.name, r.capital,
       count(d.id)       AS districts,
       round(r.area_km2) AS area_km2
FROM core.admin_region r
LEFT JOIN core.admin_district d ON d.region_id = r.id
GROUP BY r.id, r.name, r.capital, r.area_km2
ORDER BY r.id;
