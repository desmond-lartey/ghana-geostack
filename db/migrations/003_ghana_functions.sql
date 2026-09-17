-- 003_ghana_functions.sql
-- Country constants and helpers, so no query ever hardcodes a bbox or an
-- SRID again. Mirrors config/ghana.yml — if you change one, change both.

BEGIN;

-- ── Constants ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION core.gh_bbox() RETURNS geometry
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ST_MakeEnvelope(-3.30, 4.50, 1.25, 11.20, 4326);
$$;
COMMENT ON FUNCTION core.gh_bbox() IS
  'Ghana land and coastal envelope in EPSG:4326. Use as the first filter in '
  'any query against a national table — it is index-accelerated via &&.';

CREATE OR REPLACE FUNCTION core.gh_metric_srid() RETURNS integer
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 32630; $$;
COMMENT ON FUNCTION core.gh_metric_srid() IS
  'WGS 84 / UTM 30N. The CRS every length, area and buffer is computed in. '
  'Ghana crosses 0 degrees, so the far eastern strip sits slightly outside '
  'zone 30; scale error stays under ~0.1%, acceptable for analysis but not '
  'for cadastral survey.';

-- ── Measurement helpers ────────────────────────────────────────────────────
-- These exist because "area in square metres" computed on a 4326 geometry is
-- the most common silent error in spatial SQL. Square degrees are not metres.

CREATE OR REPLACE FUNCTION core.gh_area_m2(geom geometry) RETURNS double precision
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ST_Area(ST_Transform(ST_SetSRID($1, 4326), 32630));
$$;

CREATE OR REPLACE FUNCTION core.gh_length_m(geom geometry) RETURNS double precision
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ST_Length(ST_Transform(ST_SetSRID($1, 4326), 32630));
$$;

-- Buffer in true metres but hand back 4326, so results stay joinable and
-- map-ready without the caller having to think about it.
CREATE OR REPLACE FUNCTION core.gh_buffer_m(geom geometry, metres double precision)
RETURNS geometry
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ST_Transform(
             ST_Buffer(ST_Transform(ST_SetSRID($1, 4326), 32630), $2),
             4326);
$$;

CREATE OR REPLACE FUNCTION core.gh_distance_m(a geometry, b geometry)
RETURNS double precision
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ST_Distance(ST_Transform(ST_SetSRID($1, 4326), 32630),
                       ST_Transform(ST_SetSRID($2, 4326), 32630));
$$;

-- ── Name normalisation ─────────────────────────────────────────────────────
-- Ghanaian place names arrive spelled several ways across sources: Sekondi
-- Takoradi / Sekondi-Takoradi, Cape Coast / Cape-Coast, Ashanti / Asante.
-- Normalise before joining on a name, always.

CREATE OR REPLACE FUNCTION core.gh_normalise_name(txt text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT regexp_replace(
             lower(unaccent(trim(coalesce($1, '')))),
             '[^a-z0-9]+', ' ', 'g'
           );
$$;
COMMENT ON FUNCTION core.gh_normalise_name(text) IS
  'Lowercase, strip diacritics, collapse punctuation to single spaces. Join '
  'on this, never on the raw name column.';

-- ── Geometry hygiene ───────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION core.gh_clean(geom geometry) RETURNS geometry
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ST_CollectionExtract(
             ST_MakeValid(ST_SetSRID($1, 4326)),
             CASE ST_Dimension($1) WHEN 0 THEN 1 WHEN 1 THEN 2 ELSE 3 END
           );
$$;
COMMENT ON FUNCTION core.gh_clean(geometry) IS
  'Repair, then keep only the dimension we started with. ST_MakeValid alone '
  'can return a collection mixing points and lines into a polygon table, '
  'which breaks the typed column on insert.';

-- ── Registration helper ────────────────────────────────────────────────────
-- Called at the end of every load so meta.dataset never drifts from reality.

CREATE OR REPLACE FUNCTION meta.register(
    p_id          text,
    p_schema      text,
    p_table       text,
    p_title       text,
    p_theme       text,
    p_source      text,
    p_licence     text,
    p_attribution text,
    p_publishable boolean DEFAULT false
) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_count bigint;
    v_srid  integer;
    v_bbox  geometry;
    v_type  text;
BEGIN
    EXECUTE format('SELECT count(*) FROM %I.%I', p_schema, p_table) INTO v_count;

    SELECT srid, type INTO v_srid, v_type
    FROM geometry_columns
    WHERE f_table_schema = p_schema AND f_table_name = p_table
    LIMIT 1;

    IF v_srid IS NOT NULL THEN
        EXECUTE format(
            'SELECT ST_SetSRID(ST_Extent(geom)::geometry, %s) FROM %I.%I',
            v_srid, p_schema, p_table) INTO v_bbox;
    END IF;

    INSERT INTO meta.dataset (
        id, schema_name, table_name, title, theme,
        source_name, licence, attribution,
        srid, geometry_type, bbox, feature_count, publishable)
    VALUES (
        p_id, p_schema, p_table, p_title, p_theme,
        p_source, p_licence, p_attribution,
        coalesce(v_srid, 4326), v_type, v_bbox, v_count, p_publishable)
    ON CONFLICT (id) DO UPDATE SET
        title         = EXCLUDED.title,
        theme         = EXCLUDED.theme,
        source_name   = EXCLUDED.source_name,
        licence       = EXCLUDED.licence,
        attribution   = EXCLUDED.attribution,
        srid          = EXCLUDED.srid,
        geometry_type = EXCLUDED.geometry_type,
        bbox          = EXCLUDED.bbox,
        feature_count = EXCLUDED.feature_count,
        publishable   = EXCLUDED.publishable;
END;
$$;

COMMIT;
