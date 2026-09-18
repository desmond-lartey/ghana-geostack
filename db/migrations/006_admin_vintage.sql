-- 006_admin_vintage.sql
-- Boundaries change. Ghana's changed twice in the last fifteen years and will
-- change again, so the schema treats a boundary set as a dated version rather
-- than as a fact.
--
-- The design keeps `core.admin_region` and `core.admin_district` as the
-- CURRENT boundaries, because every foreign key in the database points at
-- them and a view cannot carry a foreign key. Superseded sets move to the
-- archive tables, and the mapping between them lives in the lineage table.
--
-- Loading a newer boundary set is therefore: archive what is there, load the
-- new one, record what became what. `pipelines/01b_load_geoboundaries.py`
-- does exactly that, and does not care how many regions the file contains.

BEGIN;

SET search_path TO core, public;

-- ── Vintage on the current tables ──────────────────────────────────────────

ALTER TABLE core.admin_region
    ADD COLUMN IF NOT EXISTS vintage    text,
    ADD COLUMN IF NOT EXISTS valid_from date,
    ADD COLUMN IF NOT EXISTS shape_id   text;

ALTER TABLE core.admin_district
    ADD COLUMN IF NOT EXISTS vintage    text,
    ADD COLUMN IF NOT EXISTS valid_from date,
    ADD COLUMN IF NOT EXISTS shape_id   text;

COMMENT ON COLUMN core.admin_region.vintage IS
  'Which boundary configuration this row belongs to, e.g. ''2012-2018'' or '
  '''2019-''. Rows in this table are always the current set; superseded sets '
  'live in core.admin_region_archive.';

COMMENT ON COLUMN core.admin_region.shape_id IS
  'Upstream identifier, e.g. a geoBoundaries shapeID. Kept so a reload can be '
  'matched back to its source row.';

-- ── Archive ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.admin_region_archive (
    archive_id    bigserial PRIMARY KEY,
    id            text NOT NULL,
    name          text NOT NULL,
    name_norm     text,
    capital       text,
    vintage       text NOT NULL,
    valid_from    date,
    valid_to      date,
    shape_id      text,
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    area_km2      double precision,
    source_id     text,
    superseded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, vintage)
);

CREATE TABLE IF NOT EXISTS core.admin_district_archive (
    archive_id    bigserial PRIMARY KEY,
    id            text NOT NULL,
    name          text NOT NULL,
    name_norm     text,
    region_id     text,
    region_name   text,
    assembly_type text,
    vintage       text NOT NULL,
    valid_from    date,
    valid_to      date,
    shape_id      text,
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    area_km2      double precision,
    source_id     text,
    superseded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, vintage)
);

CREATE INDEX IF NOT EXISTS admin_region_archive_geom_idx
    ON core.admin_region_archive USING GIST (geom);
CREATE INDEX IF NOT EXISTS admin_district_archive_geom_idx
    ON core.admin_district_archive USING GIST (geom);
CREATE INDEX IF NOT EXISTS admin_region_archive_vintage_idx
    ON core.admin_region_archive (vintage);
CREATE INDEX IF NOT EXISTS admin_district_archive_vintage_idx
    ON core.admin_district_archive (vintage);

COMMENT ON TABLE core.admin_region_archive IS
  'Superseded region boundary sets. The reason to keep them: data collected '
  'under an older configuration — the 2010 census, older health and '
  'agricultural surveys — cannot be placed on a current map without the '
  'geometry it was collected against.';

-- ── Lineage: what became what ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.admin_region_lineage (
    id                bigserial PRIMARY KEY,
    predecessor_name  text NOT NULL,
    predecessor_norm  text GENERATED ALWAYS AS (core.gh_normalise_name(predecessor_name)) STORED,
    successor_id      text,
    successor_name    text NOT NULL,
    successor_norm    text GENERATED ALWAYS AS (core.gh_normalise_name(successor_name)) STORED,
    change_type       text NOT NULL CHECK (change_type IN
                      ('unchanged','renamed','split','merged','created','abolished')),
    effective_date    date,
    share_hint        text,
    note              text
);

CREATE INDEX IF NOT EXISTS region_lineage_pred_idx ON core.admin_region_lineage (predecessor_norm);
CREATE INDEX IF NOT EXISTS region_lineage_succ_idx ON core.admin_region_lineage (successor_norm);

COMMENT ON TABLE core.admin_region_lineage IS
  'Crosswalk from the pre-2019 ten-region configuration to the current '
  'sixteen. Use it to attribute data collected under the old regions, but '
  'note that a split is not a clean apportionment: a value recorded for Brong '
  'Ahafo cannot be divided between Bono, Bono East and Ahafo without an '
  'assumption about how it was distributed. The share_hint column records '
  'what that assumption should be based on, not a number to multiply by.';

CREATE TABLE IF NOT EXISTS core.admin_district_lineage (
    id                bigserial PRIMARY KEY,
    predecessor_name  text NOT NULL,
    predecessor_norm  text GENERATED ALWAYS AS (core.gh_normalise_name(predecessor_name)) STORED,
    successor_id      text,
    successor_name    text NOT NULL,
    successor_norm    text GENERATED ALWAYS AS (core.gh_normalise_name(successor_name)) STORED,
    change_type       text NOT NULL CHECK (change_type IN
                      ('unchanged','renamed','split','merged','created','abolished')),
    effective_date    date,
    note              text
);

CREATE INDEX IF NOT EXISTS district_lineage_pred_idx ON core.admin_district_lineage (predecessor_norm);

-- ── Seed: the 2018-19 regional reorganisation ──────────────────────────────
-- Six new regions were created following referendums held on 27 December
-- 2018, formalised by constitutional instruments in February 2019. The date
-- below is the formalisation; verify it against the relevant CI before
-- quoting it in anything official.

DELETE FROM core.admin_region_lineage WHERE effective_date = DATE '2019-02-12';

INSERT INTO core.admin_region_lineage
    (predecessor_name, successor_name, change_type, effective_date, share_hint, note)
VALUES
    -- Brong Ahafo was dissolved entirely into three regions.
    ('Brong Ahafo', 'Bono',          'split', '2019-02-12', 'population', 'Capital Sunyani, retained from Brong Ahafo'),
    ('Brong Ahafo', 'Bono East',     'split', '2019-02-12', 'population', 'Capital Techiman'),
    ('Brong Ahafo', 'Ahafo',         'split', '2019-02-12', 'population', 'Capital Goaso'),

    -- Northern kept its name and its capital, but lost territory both ways.
    ('Northern',    'Northern',      'split', '2019-02-12', 'population', 'Retained name and capital Tamale, reduced extent'),
    ('Northern',    'Savannah',      'split', '2019-02-12', 'area',       'Capital Damongo. Largest of the new regions by area, sparsely populated'),
    ('Northern',    'North East',    'split', '2019-02-12', 'population', 'Capital Nalerigu'),

    ('Volta',       'Volta',         'split', '2019-02-12', 'population', 'Retained name and capital Ho, reduced extent'),
    ('Volta',       'Oti',           'split', '2019-02-12', 'population', 'Capital Dambai'),

    ('Western',     'Western',       'split', '2019-02-12', 'population', 'Retained name and capital Sekondi-Takoradi, reduced extent'),
    ('Western',     'Western North', 'split', '2019-02-12', 'population', 'Capital Sefwi Wiawso'),

    -- Unchanged by the reorganisation.
    ('Ashanti',       'Ashanti',       'unchanged', '2019-02-12', NULL, NULL),
    ('Central',       'Central',       'unchanged', '2019-02-12', NULL, NULL),
    ('Eastern',       'Eastern',       'unchanged', '2019-02-12', NULL, NULL),
    ('Greater Accra', 'Greater Accra', 'unchanged', '2019-02-12', NULL, NULL),
    ('Upper East',    'Upper East',    'unchanged', '2019-02-12', NULL, NULL),
    ('Upper West',    'Upper West',    'unchanged', '2019-02-12', NULL, NULL);

-- Resolve successor_id where the current region table already holds a match,
-- so the crosswalk is joinable. Left NULL until the sixteen-region set lands.
UPDATE core.admin_region_lineage l
SET successor_id = r.id
FROM core.admin_region r
WHERE r.name_norm = l.successor_norm
  AND l.successor_id IS DISTINCT FROM r.id;

-- ── Gazetteer ──────────────────────────────────────────────────────────────
-- One flat searchable list of named places, which is the shape a search or
-- lookup interface actually wants. Admin units now; settlements, facilities
-- and catchments join it as they load.

CREATE OR REPLACE VIEW core.gazetteer AS
SELECT 'GHA'::text                 AS place_id,
       'ADM0'::text                AS level,
       name                        AS place_name,
       core.gh_normalise_name(name) AS place_norm,
       NULL::text                  AS parent_id,
       NULL::text                  AS parent_name,
       round(area_km2::numeric, 1) AS area_km2,
       ST_PointOnSurface(geom)     AS point,
       geom
FROM core.admin_country

UNION ALL
SELECT r.id, 'ADM1', r.name, r.name_norm, 'GHA', 'Ghana',
       round(r.area_km2::numeric, 1), ST_PointOnSurface(r.geom), r.geom
FROM core.admin_region r

UNION ALL
SELECT d.id, 'ADM2', d.name, d.name_norm, d.region_id, r.name,
       round(d.area_km2::numeric, 1), ST_PointOnSurface(d.geom), d.geom
FROM core.admin_district d
LEFT JOIN core.admin_region r ON r.id = d.region_id;

COMMENT ON VIEW core.gazetteer IS
  'Flat searchable place list. Match user input against place_norm using '
  'pg_trgm similarity rather than equality — Ghanaian place names are spelled '
  'several ways and users type them a fourth.';

-- ── Archive helper ─────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION core.archive_admin(p_valid_to date DEFAULT current_date)
RETURNS TABLE (regions bigint, districts bigint)
LANGUAGE plpgsql AS $$
DECLARE
    r_count bigint;
    d_count bigint;
BEGIN
    INSERT INTO core.admin_region_archive
        (id, name, name_norm, capital, vintage, valid_from, valid_to,
         shape_id, geom, area_km2, source_id)
    SELECT id, name, name_norm, capital,
           coalesce(vintage, 'unknown'), valid_from, p_valid_to,
           shape_id, geom, area_km2, source_id
    FROM core.admin_region
    ON CONFLICT (id, vintage) DO NOTHING;
    GET DIAGNOSTICS r_count = ROW_COUNT;

    INSERT INTO core.admin_district_archive
        (id, name, name_norm, region_id, region_name, assembly_type, vintage,
         valid_from, valid_to, shape_id, geom, area_km2, source_id)
    SELECT d.id, d.name, d.name_norm, d.region_id, r.name, d.assembly_type,
           coalesce(d.vintage, 'unknown'), d.valid_from, p_valid_to,
           d.shape_id, d.geom, d.area_km2, d.source_id
    FROM core.admin_district d
    LEFT JOIN core.admin_region r ON r.id = d.region_id
    ON CONFLICT (id, vintage) DO NOTHING;
    GET DIAGNOSTICS d_count = ROW_COUNT;

    RETURN QUERY SELECT r_count, d_count;
END;
$$;

COMMENT ON FUNCTION core.archive_admin(date) IS
  'Copy the current boundary set into the archive before replacing it. Call '
  'this before loading a new vintage, never after.';

COMMIT;
