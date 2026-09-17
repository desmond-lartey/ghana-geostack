# Ghana GeoStack

An open spatial data platform for Ghana. PostGIS for the authoritative store,
DuckDB for the portable path, GeoParquet for interchange, vector tiles and an
OGC API for the web, and an agent skill that writes and **validates** the SQL.

Built on two pieces of prior work:

- [rafimt/geospatial-data-pipeline](https://github.com/rafimt/geospatial-data-pipeline) — the pipeline architecture
- [dekart-xyz/geosql](https://github.com/dekart-xyz/geosql) (MIT) — the agent workflow with validation in the loop

---

## Why this exists

Spatial data about Ghana is scattered across a dozen portals in a dozen
formats, most of it undocumented, much of it in the wrong coordinate system,
and almost none of it queryable without first downloading a shapefile and
opening a desktop GIS. This is one database, one catalogue, one set of
conventions, and several ways to get at it depending on what you have.

The thing worth copying from GeoSQL is the discipline: **no result is
presented until it has been checked in SQL.** Row counts, total areas,
coordinate systems, features that fall outside the country. Every analysis
file ends with a validation block, and `make qc` fails the build if the
numbers are implausible for Ghana. A map you cannot check is a map you cannot
use.

---

## Quick start

```bash
git clone https://github.com/YOUR-ORG/ghana-geostack
cd ghana-geostack
cp .env.example .env

make up                 # PostGIS + tile server + feature server + TiTiler
make pipeline           # fetch, load, analyse, validate, export
make serve              # http://localhost:8080/web/
```

First run takes a while — Ghana's building footprints are millions of
polygons. For something quicker:

```bash
make up && make migrate
make fetch-accra        # Greater Accra only
make load analysis qc
```

### No Docker, no database

The exports are the point. One file, real SQL, works offline.

```bash
duckdb -init duckdb/bootstrap.sql
```

```sql
SELECT name, round(area_km2) AS km2, population
FROM ghana.region ORDER BY km2 DESC;
```

---

## What is in it

| Theme | Layers | Source |
| --- | --- | --- |
| Administrative | 16 regions, ~261 districts (MMDAs) | GADM now, GSS/GRID3 when obtained |
| Buildings | Footprints with height, class, confidence | Overture, Google Open Buildings, OSM |
| Transport | Road network, classified and normalised | OpenStreetMap |
| Population | 100 m gridded population | WorldPop |
| Facilities | Health, education, market, water, energy | healthsites.io, OSM |
| Terrain | 30 m elevation and slope | Copernicus DEM GLO-30 |
| Land cover | 10 m classes | ESA WorldCover |
| Hydrology | Rivers, streams, surface water | OSM, HydroSHEDS, JRC |

Full catalogue with licences: [`config/sources.yml`](config/sources.yml).
Live catalogue once loaded: `SELECT * FROM meta.dataset;`

### Analyses that ship with it

- **Health and school accessibility** — distance from every building to the
  nearest facility, rolled up by district against the 5 km CHPS catchment
- **Flood exposure** — buildings on low ground near watercourses. Observed
  historical water and terrain, not a modelled flood risk
- **Building density** — H3 hexes, because district choropleths in Ghana
  mostly show how big the districts are
- **Siting suitability** — a weighted score with the weights in a visible
  table and the components kept alongside the total

---

## How it is put together

```
Sources ──► pipelines/ ──► PostGIS ──► analysis ──► QC ──► exports ──► web
  OSM         fetch         raw         SQL        SQL     GeoParquet   MapLibre
  Overture    validate      core        idempotent fails   DuckDB file  tiles
  WorldPop    load          analysis    rebuildable build  PMTiles      OGC API
  Copernicus  register      serve                          attribution  DuckDB-WASM
```

Six schemas, each with one job:

| Schema | Holds |
| --- | --- |
| `raw` | Untouched loads. Reproducible from `sources.yml` alone |
| `core` | Curated, conformed, documented. What you query |
| `analysis` | Derived results. Always rebuildable from `core` |
| `h3` | Equal-area hex rollups at three resolutions |
| `serve` | Thin views. The only schema the tile and feature servers see |
| `meta` | Dataset registry, QC runs, lineage |

### Services

| Service | Port | What for |
| --- | --- | --- |
| PostGIS | 5432 | The database |
| pg_tileserv | 7800 | Vector tiles straight from SQL |
| pg_featureserv | 9000 | OGC API — Features, GeoJSON over HTTP |
| TiTiler | 8001 | Dynamic raster tiles from COGs |
| MinIO | 9001 | S3-compatible store for the GeoParquet lake |

---

## Using it with Claude

The `ghana-geosql` skill teaches an agent this database specifically: the
schema, Ghana's place-name ambiguities, the coordinate systems, and the
validation it must do before showing you anything.

```bash
cp -r skills/ghana-geosql ~/.claude/skills/
```

Then:

```
/ghana-geosql Map health facility access across the Upper West Region
/ghana-geosql Which districts have the most buildings on flood-prone land?
/ghana-geosql Compare road density between Ashanti and Northern
```

The skill will discover the schema, resolve the place name against the
database rather than guessing, write the SQL, run the validation block, and
only then draw a map. If the data to answer the question does not exist, it
says so instead of approximating.

Evals for that behaviour are in [`evals/evals.json`](evals/evals.json).

---

## Conventions worth knowing before contributing

**Store in EPSG:4326, measure in EPSG:32630.** Ghana straddles the prime
meridian, so no UTM zone fits perfectly; 32630 gives under ~0.1% scale error
in the eastern strip, which is fine for analysis and not fine for cadastral
work. Use `core.gh_area_m2()` and friends — `ST_Area` on a 4326 geometry
returns square degrees, and the number looks plausible. See
[`docs/crs.md`](skills/ghana-geosql/references/crs.md).

**Two filters on every spatial join.** `&&` for the index gate, then
`ST_Intersects` for correctness. Neither alone is right.

**Nothing is publishable by default.** `meta.dataset.publishable` starts
false. The export step refuses to write anything that has not been cleared,
and QC fails a build where a publishable dataset has no attribution string.
GADM is non-commercial. OSM is ODbL share-alike. These are obligations, not
formalities.

**Say what the data is.** Observed surface water is not modelled flood risk.
Straight-line distance is not travel time. Modelled population is not a census
count. Every one of those distinctions matters to whoever reads the map next.

Full guidance for humans and agents: [`AGENTS.md`](AGENTS.md),
[`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Status and what is missing

This is early. The scaffolding is complete and the conventions are settled;
the data is not all loaded and some of it needs agreements we do not yet have.

Known gaps, stated plainly rather than papered over:

- **Authoritative boundaries.** GADM's districts predate the 2018-19
  reorganisation and its licence is non-commercial. The Ghana Statistical
  Service set is the one we want and needs a data request.
- **No electricity grid layer**, so siting analysis uses road distance as a
  weak remoteness proxy.
- **No travel-time surface.** Everything is straight-line distance, which
  understates real journeys badly in the rainy season.
- **No engineered flood model.**
- **No cadastral or land-tenure data**, which is simultaneously the most
  requested layer and the hardest to obtain.

See [`ROADMAP.md`](ROADMAP.md).

---

## Licence

Code: MIT, see [`LICENSE`](LICENSE).

Data: **not** MIT. Each dataset keeps its own licence, and several of them
restrict what you may do. Read [`LICENSE-DATA.md`](LICENSE-DATA.md) before
publishing anything derived from this.
