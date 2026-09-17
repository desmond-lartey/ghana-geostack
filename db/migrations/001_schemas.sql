-- 001_schemas.sql
-- Five schemas, each with one job. Data flows strictly left to right:
--   raw -> core -> analysis -> serve
-- and meta watches all of it.

BEGIN;

CREATE SCHEMA IF NOT EXISTS raw;
COMMENT ON SCHEMA raw IS
  'Untouched loads, exactly as they came from source. Reproducible from '
  'sources.yml alone. Nothing here is edited by hand and nothing here is '
  'served to users.';

CREATE SCHEMA IF NOT EXISTS core;
COMMENT ON SCHEMA core IS
  'Curated and conformed. Consistent SRID, valid geometry, stable column '
  'names, documented columns, joined to admin boundaries. This is the layer '
  'analysts and the agent are pointed at.';

CREATE SCHEMA IF NOT EXISTS analysis;
COMMENT ON SCHEMA analysis IS
  'Derived results: buffers, accessibility, exposure, suitability, clusters. '
  'Always rebuildable from core by re-running db/analysis/*.sql.';

CREATE SCHEMA IF NOT EXISTS h3;
COMMENT ON SCHEMA h3 IS
  'Hex-grid rollups. Resolution 5 for national views, 7 regional, 9 urban.';

CREATE SCHEMA IF NOT EXISTS serve;
COMMENT ON SCHEMA serve IS
  'Thin views holding only the columns a map or API response needs. This is '
  'the only schema exposed to pg_tileserv and pg_featureserv.';

CREATE SCHEMA IF NOT EXISTS meta;
COMMENT ON SCHEMA meta IS
  'Dataset registry, quality-control runs, lineage. The answer to "where did '
  'this number come from" lives here.';

-- Read-only role for the tile and feature servers. They should never be able
-- to write, and should not see raw or analysis internals.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ghana_read') THEN
        CREATE ROLE ghana_read NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA core, serve, h3, meta TO ghana_read;
GRANT SELECT ON ALL TABLES IN SCHEMA core, serve, h3, meta TO ghana_read;
ALTER DEFAULT PRIVILEGES IN SCHEMA core, serve, h3, meta
    GRANT SELECT ON TABLES TO ghana_read;

COMMIT;
