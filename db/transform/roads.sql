-- transform/roads.sql - raw.road into core.road
--
-- OSM's highway tag carries about 30 values; downstream styling and analysis
-- only care about a handful. The rest are kept but grouped, so a query for
-- 'primary' does not silently miss 'primary_link'.

\set ON_ERROR_STOP on
SET search_path TO core, raw, public;

BEGIN;

TRUNCATE core.road;

INSERT INTO core.road
    (osm_id, name, class, surface, oneway, lanes, district_id, geom, source_id)
SELECT
    CASE WHEN r.id ~ '^[0-9]+$' THEN r.id::bigint END,
    nullif(r.name, ''),
    CASE
        WHEN r.class IN ('motorway','motorway_link')   THEN 'motorway'
        WHEN r.class IN ('trunk','trunk_link')         THEN 'trunk'
        WHEN r.class IN ('primary','primary_link')     THEN 'primary'
        WHEN r.class IN ('secondary','secondary_link') THEN 'secondary'
        WHEN r.class IN ('tertiary','tertiary_link')   THEN 'tertiary'
        WHEN r.class IN ('residential','living_street','unclassified') THEN 'local'
        WHEN r.class IN ('track','path','footway','cycleway','bridleway') THEN 'track'
        ELSE coalesce(nullif(r.class, ''), 'other')
    END,
    nullif(r.surface, ''),
    CASE lower(coalesce(r.oneway, '')) WHEN 'yes' THEN true WHEN 'no' THEN false END,
    CASE WHEN r.lanes ~ '^[0-9]+$' THEN r.lanes::smallint END,
    d.id,
    -- Multi-part lines are split so that length and district assignment mean
    -- something for each piece.
    (ST_Dump(core.gh_clean(r.geometry))).geom::geometry(LineString, 4326),
    r.source_id
FROM raw.road r
LEFT JOIN core.admin_district d
       ON ST_Contains(d.geom, ST_LineInterpolatePoint(ST_GeometryN(r.geometry, 1), 0.5))
WHERE r.geometry IS NOT NULL
  AND r.geometry && core.gh_bbox();

COMMIT;

ANALYZE core.road;

SELECT 'road segments'   AS check, count(*)::text AS value FROM core.road
UNION ALL
SELECT 'network length (km)',
       round((sum(length_m)/1000)::numeric)::text FROM core.road
UNION ALL
SELECT 'paved network (km)',
       round((sum(length_m) FILTER (WHERE surface IN ('asphalt','paved','concrete'))/1000)::numeric)::text
       FROM core.road
UNION ALL
SELECT 'trunk and primary (km)',
       round((sum(length_m) FILTER (WHERE class IN ('trunk','primary'))/1000)::numeric)::text
       FROM core.road
UNION ALL
SELECT 'segments with no district', count(*)::text FROM core.road WHERE district_id IS NULL;

-- Ghana's classified road network is roughly 78,000 km, of which a minority
-- is paved. OSM includes unclassified tracks, so a total well above that is
-- expected; a total far below it means a partial extract.
