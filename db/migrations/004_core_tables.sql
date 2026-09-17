-- 004_core_tables.sql
-- The canonical Ghana layers. Typed geometry columns with an explicit SRID,
-- so a wrong-CRS insert fails loudly at write time instead of producing a
-- map centred on the Gulf of Guinea.
--
-- Naming convention: singular noun, theme prefix. admin_region, not regions.

BEGIN;

-- ── Administrative hierarchy ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.admin_country (
    id          text PRIMARY KEY DEFAULT 'GHA',
    name        text NOT NULL,
    geom        geometry(MultiPolygon, 4326) NOT NULL,
    area_km2    double precision GENERATED ALWAYS AS
                (ST_Area(ST_Transform(geom, 32630)) / 1e6) STORED,
    source_id   text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.admin_region (
    id           text PRIMARY KEY,                 -- stable code, e.g. GH-AA
    name         text NOT NULL,
    name_norm    text GENERATED ALWAYS AS (core.gh_normalise_name(name)) STORED,
    capital      text,
    country_id   text NOT NULL DEFAULT 'GHA' REFERENCES core.admin_country(id),
    geom         geometry(MultiPolygon, 4326) NOT NULL,
    area_km2     double precision GENERATED ALWAYS AS
                 (ST_Area(ST_Transform(geom, 32630)) / 1e6) STORED,
    population   bigint,                           -- 2021 PHC where available
    source_id    text,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.admin_district (
    id           text PRIMARY KEY,
    name         text NOT NULL,
    name_norm    text GENERATED ALWAYS AS (core.gh_normalise_name(name)) STORED,
    region_id    text NOT NULL REFERENCES core.admin_region(id),
    -- MMDA class matters for policy questions and is regularly asked for.
    assembly_type text CHECK (assembly_type IN
                  ('metropolitan','municipal','district')),
    capital      text,
    geom         geometry(MultiPolygon, 4326) NOT NULL,
    area_km2     double precision GENERATED ALWAYS AS
                 (ST_Area(ST_Transform(geom, 32630)) / 1e6) STORED,
    population   bigint,
    source_id    text,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS admin_region_geom_idx   ON core.admin_region   USING GIST (geom);
CREATE INDEX IF NOT EXISTS admin_district_geom_idx ON core.admin_district USING GIST (geom);
CREATE INDEX IF NOT EXISTS admin_district_region_idx ON core.admin_district (region_id);
CREATE INDEX IF NOT EXISTS admin_region_name_trgm  ON core.admin_region   USING GIN (name_norm gin_trgm_ops);
CREATE INDEX IF NOT EXISTS admin_district_name_trgm ON core.admin_district USING GIN (name_norm gin_trgm_ops);

-- ── Transport ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.road (
    id            bigserial PRIMARY KEY,
    osm_id        bigint,
    name          text,
    class         text NOT NULL,                   -- motorway, trunk, primary, ...
    surface       text,
    oneway        boolean,
    lanes         smallint,
    district_id   text REFERENCES core.admin_district(id),
    geom          geometry(LineString, 4326) NOT NULL,
    length_m      double precision GENERATED ALWAYS AS
                  (ST_Length(ST_Transform(geom, 32630))) STORED,
    source_id     text NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS road_geom_idx     ON core.road USING GIST (geom);
CREATE INDEX IF NOT EXISTS road_class_idx    ON core.road (class);
CREATE INDEX IF NOT EXISTS road_district_idx ON core.road (district_id);

-- ── Buildings ──────────────────────────────────────────────────────────────
-- Partitioned by region: Ghana has several million footprints once Google
-- Open Buildings is loaded, and almost every query is regional.

CREATE TABLE IF NOT EXISTS core.building (
    id            bigserial,
    source_ref    text,                            -- upstream id, if any
    name          text,
    class         text,                            -- residential, commercial, ...
    height_m      double precision,
    levels        smallint,
    confidence    double precision,                -- ML sources only; NULL for OSM
    district_id   text REFERENCES core.admin_district(id),
    region_id     text NOT NULL REFERENCES core.admin_region(id),
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    area_m2       double precision GENERATED ALWAYS AS
                  (ST_Area(ST_Transform(geom, 32630))) STORED,
    source_id     text NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, region_id)
) PARTITION BY LIST (region_id);

COMMENT ON COLUMN core.building.confidence IS
  'Model confidence from Google Open Buildings or Microsoft footprints. '
  'Filter at >= 0.7 for most analysis. NULL means a surveyed or OSM source, '
  'which is not the same as low confidence.';

-- Partitions are created by pipelines/20_load_postgis.py from the region list,
-- so a new region does not need a migration. Default catches anything
-- unmatched rather than rejecting the insert.
CREATE TABLE IF NOT EXISTS core.building_unassigned
    PARTITION OF core.building DEFAULT;

-- ── Population ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.population_grid (
    id          bigserial PRIMARY KEY,
    year        smallint NOT NULL,
    population  double precision NOT NULL,
    district_id text REFERENCES core.admin_district(id),
    geom        geometry(Polygon, 4326) NOT NULL,   -- 100 m cell footprint
    source_id   text NOT NULL
);

CREATE INDEX IF NOT EXISTS population_grid_geom_idx ON core.population_grid USING GIST (geom);
CREATE INDEX IF NOT EXISTS population_grid_year_idx ON core.population_grid (year);

-- ── Points of service ──────────────────────────────────────────────────────
-- Health, education and markets share one shape. Splitting them into three
-- near-identical tables buys nothing and triples the join work.

CREATE TABLE IF NOT EXISTS core.facility (
    id            bigserial PRIMARY KEY,
    source_ref    text,
    name          text,
    category      text NOT NULL CHECK (category IN
                  ('health','education','market','water','energy','government','other')),
    subtype       text,                            -- CHPS compound, JHS, clinic...
    ownership     text,                            -- public, private, mission, NGO
    district_id   text REFERENCES core.admin_district(id),
    geom          geometry(Point, 4326) NOT NULL,
    source_id     text NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS facility_geom_idx     ON core.facility USING GIST (geom);
CREATE INDEX IF NOT EXISTS facility_category_idx ON core.facility (category, subtype);
CREATE INDEX IF NOT EXISTS facility_district_idx ON core.facility (district_id);

-- ── Hydrology ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.waterway (
    id          bigserial PRIMARY KEY,
    name        text,
    class       text,                              -- river, stream, canal, drain
    is_seasonal boolean,
    geom        geometry(LineString, 4326) NOT NULL,
    length_m    double precision GENERATED ALWAYS AS
                (ST_Length(ST_Transform(geom, 32630))) STORED,
    source_id   text NOT NULL
);

CREATE INDEX IF NOT EXISTS waterway_geom_idx ON core.waterway USING GIST (geom);

-- ── Land cover ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.landcover (
    id          bigserial PRIMARY KEY,
    class_code  smallint NOT NULL,                 -- ESA WorldCover code
    class_name  text NOT NULL,
    year        smallint NOT NULL,
    district_id text REFERENCES core.admin_district(id),
    geom        geometry(MultiPolygon, 4326) NOT NULL,
    area_m2     double precision GENERATED ALWAYS AS
                (ST_Area(ST_Transform(geom, 32630))) STORED,
    source_id   text NOT NULL
);

CREATE INDEX IF NOT EXISTS landcover_geom_idx  ON core.landcover USING GIST (geom);
CREATE INDEX IF NOT EXISTS landcover_class_idx ON core.landcover (class_code, year);

-- ── Raster coverages ───────────────────────────────────────────────────────
-- Tiled in-db rasters for terrain. Large imagery stays as COGs on object
-- storage and is served through TiTiler; only analysis-critical bands land here.

CREATE TABLE IF NOT EXISTS core.dem (
    rid   serial PRIMARY KEY,
    rast  raster NOT NULL,
    source_id text NOT NULL DEFAULT 'dem_copernicus_30'
);

CREATE INDEX IF NOT EXISTS dem_rast_idx ON core.dem USING GIST (ST_ConvexHull(rast));

CREATE TABLE IF NOT EXISTS core.slope (
    rid   serial PRIMARY KEY,
    rast  raster NOT NULL,
    source_id text NOT NULL DEFAULT 'dem_copernicus_30'
);

CREATE INDEX IF NOT EXISTS slope_rast_idx ON core.slope USING GIST (ST_ConvexHull(rast));

COMMIT;
