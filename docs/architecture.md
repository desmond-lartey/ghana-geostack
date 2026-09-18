# Architecture

## The shape of it

```
                    config/sources.yml - nothing enters without a licence
                              │
   ┌──────────────────────────┼──────────────────────────┐
   │                          │                          │
OSM/Geofabrik          Overture on S3            STAC (Copernicus,
Google Open Buildings  (DuckDB, no download)      WorldCover, Sentinel)
   │                          │                          │
   └──────────────────────────┴──────────────────────────┘
                              │  pipelines/0*  fetch + validate
                              ▼
                        ┌───────────┐
                        │   raw     │  untouched, reproducible
                        └─────┬─────┘
                              │  db/transform/*  conform, clean, join to admin
                              ▼
                        ┌───────────┐
                        │   core    │  ← this is what you query
                        └─────┬─────┘
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
             ┌────────┐  ┌────────┐  ┌────────┐
             │analysis│  │   h3   │  │  meta  │  registry, QC, lineage
             └────┬───┘  └───┬────┘  └────────┘
                  └──────┬───┘
                         ▼
                   ┌───────────┐
                   │   serve   │  thin views, the only public schema
                   └─────┬─────┘
          ┌──────────────┼──────────────┬──────────────┐
          ▼              ▼              ▼              ▼
     pg_tileserv   pg_featureserv   GeoParquet     ghana.duckdb
     vector tiles   OGC Features    + PMTiles      one file, offline
          └──────────────┴──────────────┴──────────────┘
                         ▼
              web/index.html  ·  QGIS  ·  Python  ·  R  ·  the agent skill
```

## Why each piece is there

**PostGIS is authoritative.** Typed geometry columns with declared SRIDs mean
a wrong-CRS insert fails at write time rather than producing a map centred on
the Gulf of Guinea. Rasters, routing and partitioning all live here.

**DuckDB is the portable path.** No server, no credentials, reads GeoParquet
and remote Overture directly, runs in a browser via WebAssembly. This matters
more than it might look: a lot of the people who should be using Ghanaian
spatial data are not going to run Docker, and connectivity is not guaranteed.
The exports are a first-class output, not a convenience.

**GeoParquet is the interchange format.** Columnar, compressed, readable by
every modern tool, and supports range requests so a client fetches only the
columns and row groups it needs.

**Six schemas, one job each.** The separation is what makes the pipeline
rerunnable: `analysis` is always rebuildable from `core`, and `core` is always
rebuildable from `raw`, and `raw` is always rebuildable from `sources.yml`.
Nothing is edited in place, so nothing is unrecoverable.

**`serve` is the only public surface.** The tile and feature servers see one
schema, holding thin views with the minimum columns a map needs. Internal ids,
timestamps and provenance stay behind it.

**`meta` is the part people skip and regret.** The dataset registry answers
"where did this number come from", the QC tables answer "was this build any
good", and the `publishable` flag is what stands between an unread licence and
a public tileset.

## The validation loop

This is the idea worth borrowing, and it comes from GeoSQL:

1. **Discover** the schema instead of assuming it
2. **Resolve** the place against the database instead of guessing coordinates
3. **Draft** the query with both the index gate and the exact predicate
4. **Validate in SQL** - row counts, total area or length in metres, extent
   inside Ghana, nulls in mapped columns, plausibility against known figures
5. **Then** render, and look at the render before describing it

It is enforced in three places, so it does not depend on anyone remembering:

- Each `db/analysis/*.sql` file ends with its own validation block
- `db/qc/checks.sql` writes every result into `meta.qc_result` and fails the
  build on an error
- `pipelines/50_export.py` refuses to export from a failed QC run

## Partitioning

`core.building` is partitioned by `region_id`. Ghana has several million
footprints once Google Open Buildings is loaded, and almost every real query
is regional, so including `region_id` in the WHERE clause touches one
partition instead of sixteen. Partitions are created from the region list at
load time, so adding a region does not require a migration.

## What is deliberately not here

- **No ETL orchestrator.** The pipeline is numbered scripts and a Makefile.
  Airflow or Dagster earns its place when there are schedules and dependencies
  worth managing; today it would be ceremony.
- **No ORM over the spatial tables.** Spatial SQL is the interface. Hiding it
  behind an ORM removes the thing that makes the database useful.
- **No microservices.** One database, a handful of stateless servers in front
  of it.
