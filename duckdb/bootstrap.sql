-- bootstrap.sql — open Ghana GeoStack in DuckDB with no server at all.
--
--   duckdb -init duckdb/bootstrap.sql
--
-- This is the low-friction path: no Docker, no Postgres, no credentials. It
-- reads the GeoParquet exports directly, which is enough for most analysis
-- and all of the reading people want to do on a laptop.

INSTALL spatial;  LOAD spatial;
INSTALL httpfs;   LOAD httpfs;
INSTALL parquet;  LOAD parquet;
INSTALL json;     LOAD json;

-- H3 is a community extension, so it is optional.
INSTALL h3 FROM community;
LOAD h3;

SET s3_region = 'us-west-2';

CREATE SCHEMA IF NOT EXISTS ghana;

-- Local exports, produced by pipelines/50_export.py.
CREATE OR REPLACE VIEW ghana.region       AS SELECT * FROM read_parquet('data/exports/core.admin_region.parquet');
CREATE OR REPLACE VIEW ghana.district     AS SELECT * FROM read_parquet('data/exports/core.admin_district.parquet');
CREATE OR REPLACE VIEW ghana.building     AS SELECT * FROM read_parquet('data/exports/core.building.parquet');
CREATE OR REPLACE VIEW ghana.road         AS SELECT * FROM read_parquet('data/exports/core.road.parquet');
CREATE OR REPLACE VIEW ghana.facility     AS SELECT * FROM read_parquet('data/exports/core.facility.parquet');

-- Ghana constants, matching core.gh_* in PostGIS so the same query shape
-- works against either engine.
CREATE OR REPLACE MACRO gh_bbox() AS
    ST_MakeEnvelope(-3.30, 4.50, 1.25, 11.20);

-- Metric measurement. DuckDB spatial transforms with PROJ, same as PostGIS.
CREATE OR REPLACE MACRO gh_area_m2(g) AS
    ST_Area(ST_Transform(g, 'EPSG:4326', 'EPSG:32630'));

CREATE OR REPLACE MACRO gh_length_m(g) AS
    ST_Length(ST_Transform(g, 'EPSG:4326', 'EPSG:32630'));

CREATE OR REPLACE MACRO gh_distance_m(a, b) AS
    ST_Distance(ST_Transform(a, 'EPSG:4326', 'EPSG:32630'),
                ST_Transform(b, 'EPSG:4326', 'EPSG:32630'));

SELECT 'Ghana GeoStack loaded. Try: SELECT name, area_km2 FROM ghana.region ORDER BY area_km2 DESC;' AS ready;
