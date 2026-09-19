-- Runs once, the first time the postgis container initialises its volume.
-- Anything that must exist before a single row is loaded belongs here.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;      -- place-name matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;            -- fuzzy search on names
CREATE EXTENSION IF NOT EXISTS unaccent;           -- normalise Akan/Ewe diacritics
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;           -- gen_random_uuid()

-- Optional, install if the image provides them. Failure here is not fatal.
DO $$
BEGIN
    BEGIN CREATE EXTENSION IF NOT EXISTS h3;      EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'h3 extension unavailable - H3 rollups will run in DuckDB instead'; END;
    BEGIN CREATE EXTENSION IF NOT EXISTS h3_postgis; EXCEPTION WHEN OTHERS THEN NULL; END;
    BEGIN CREATE EXTENSION IF NOT EXISTS pgrouting;  EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'pgrouting unavailable - network routing disabled'; END;
END
$$;

-- Raster drivers are disabled by default in PostGIS 3.x, so raster2pgsql and
-- ST_Value would fail on a fresh database. Persist the setting so it survives
-- reconnects, not just this session.
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET postgis.gdal_enabled_drivers TO %L',
                   current_database(), 'ENABLE_ALL');
    EXECUTE format('ALTER DATABASE %I SET postgis.enable_outdb_rasters TO %L',
                   current_database(), 'true');
END
$$;
