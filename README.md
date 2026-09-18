# Ghana GeoStack

An open spatial data platform for Ghana. PostGIS as the authoritative store,
DuckDB for portable analysis, GeoParquet for interchange, vector tiles and an
OGC API for the web, and an agent skill that writes and validates spatial SQL.

Administrative boundaries for all 16 regions and 260 districts ship with the
repository, so a clone is immediately useful.

---

## What it provides

| Theme | Layers | Source |
| --- | --- | --- |
| Administrative | 16 regions, 260 districts, 177 capitals, p-coded | Ghana COD-AB |
| Buildings | Footprints with height, class, confidence | Overture, Google Open Buildings, OSM |
| Transport | Classified road network | OpenStreetMap |
| Population | 100 m gridded population | WorldPop |
| Facilities | Health, education, market, water, energy | healthsites.io, OSM |
| Terrain | 30 m elevation and slope | Copernicus DEM GLO-30 |
| Land cover | 10 m classes | ESA WorldCover |
| Hydrology | Rivers, streams, surface water | OSM, HydroSHEDS, JRC |

The full catalogue, with licences, is in [`config/sources.yml`](config/sources.yml).
Once the database is loaded, `SELECT * FROM meta.dataset;` lists what is
present and what may be republished.

### Included analyses

- **Health and education accessibility** — distance from every building to the
  nearest facility, summarised by district against the 5 km CHPS catchment
- **Flood exposure** — buildings on low ground near watercourses, derived from
  observed historical surface water and terrain
- **Building density** — H3 hex rollups at national, regional and urban
  resolutions
- **Siting suitability** — weighted multi-criteria scoring with the weights
  held in a visible table and component scores retained alongside the total

---

## Installation

### Requirements

- Docker and Docker Compose
- Python 3.11 or later
- Conda recommended; the GDAL stack installs more reliably than through pip

### Setup

```bash
git clone https://github.com/YOUR-ORG/ghana-geostack
cd ghana-geostack
cp .env.example .env

conda env create -f environment.yml
conda activate ghana-geostack
```

### Running

```bash
make up          # PostGIS, pg_tileserv, pg_featureserv, TiTiler, MinIO
make pipeline    # fetch, load, analyse, validate, export
make serve       # http://localhost:8080/web/
```

The viewer works before the stack is running: it falls back to the boundaries
committed under `data/reference/`, and enables the remaining layers once
pg_tileserv is reachable.

`make pipeline` runs `migrate fetch load analysis qc export` in sequence. Each
stage is independently rerunnable, so a failure can be resumed rather than
restarted.

For a faster first run, load boundaries and a single city:

```bash
make up && make migrate
make fetch-accra
make load analysis qc
```

### Without Docker

The GeoParquet exports and the single-file DuckDB database require no server:

```bash
duckdb -init duckdb/bootstrap.sql
```

```sql
SELECT name, round(area_km2) AS km2, capital
FROM ghana.region ORDER BY km2 DESC;
```

This works offline and the Parquet files open directly in QGIS, GeoPandas, R
and ArcGIS Pro.

---

## Administrative boundaries

Boundaries come from the Ghana Common Operational Dataset (COD-AB), the
reference boundary set used for humanitarian coordination and maintained with
the national statistical authority. Version v01, valid from 8 March 2021.

Converted to GeoJSON and committed under [`data/reference/`](data/reference/):

| File | Features | Contents |
| --- | --- | --- |
| `gha_admin0.geojson` | 1 | National boundary |
| `gha_admin1.geojson` | 16 | Regions |
| `gha_admin2.geojson` | 260 | Districts (MMDAs) |
| `gha_admincapitals.geojson` | 177 | Administrative capitals |

### P-codes are the join key

Every unit carries an OCHA p-code. P-codes are stable across releases and
independent of spelling, and the hierarchy is encoded in the code itself:

```
GH        country
GH01      Ahafo            GH09      North East
GH02      Ashanti          GH10      Oti
GH03      Bono             GH11      Savannah
GH04      Bono East        GH12      Upper East
GH05      Central          GH13      Upper West
GH06      Eastern          GH14      Volta
GH07      Greater Accra    GH15      Western
GH08      Northern         GH16      Western North

GH0701    Ablekuma Central Municipal   (district 01 of region GH07)
```

Because a district p-code begins with its region p-code, the hierarchy is
resolved by string prefix rather than by a spatial join. Join on p-codes, not
on names.

Districts break down as 6 metropolitan, 65 municipal and 189 district
assemblies by the naming convention used in the source. The legal
classification is set by the instrument that created each assembly and is not
always reflected in the published name, so `assembly_type` is a working
default rather than an authority.

The source spells the North East Region as "Northern East". The transform
corrects it to the official name and retains the variant in
`core.admin_alias`, so either form resolves in search.

### Boundaries change

Ghana's administrative geography changed in 2012 and again in 2019. The schema
treats a boundary set as a dated version:

- `core.admin_region` and `core.admin_district` hold the current set
- `core.admin_region_archive` and `core.admin_district_archive` hold
  superseded sets
- `core.admin_region_lineage` maps predecessors to successors, covering the
  ten-region to sixteen-region reorganisation

Loading a newer boundary set archives the current one, loads the replacement
and records what became what. Nothing needs to be rewritten, and data
collected under an older configuration remains placeable on a map.

### Converting an updated release

The converter reads shapefiles without GDAL, GeoPandas or pyshp:

```bash
python pipelines/01_fetch_admin.py --shapefiles ~/Downloads/gha_admin_boundaries_shp
python pipelines/01_fetch_admin.py --verify
```

Verification checks feature counts, p-code format, hierarchy consistency,
geometry extent and that region and district areas agree to within 1 km².

---

## The viewer

`web/index.html` is a single self-contained file. The map fills the window and
the interface stays out of the way until asked for.

| Element | Behaviour |
| --- | --- |
| Legend, top left | Describes the active layer; collapses to its title |
| Menu, top right | Opens layers, the SQL console and sources |
| Pills, bottom left | Info, reset, locate, query — panels open only on request |
| Story, bottom right | Six-step guided tour through the data |

Layers are grouped into Administrative, Infrastructure, Services and Analysis,
and each carries its own legend and popup schema. The SQL console runs DuckDB
compiled to WebAssembly, reading GeoParquet over range requests, so queries
execute in the browser with no server involved. Results with a `geom` column
can be drawn straight onto the map.

The map opens as a globe and settles onto Ghana, handing over to a flat
projection as the camera comes in.

## Architecture

```
Sources ──► pipelines/ ──► PostGIS ──► analysis ──► QC ──► exports ──► web
```

Six schemas, each with a single responsibility:

| Schema | Contents |
| --- | --- |
| `raw` | Untouched loads, reproducible from `config/sources.yml` |
| `core` | Curated and conformed. The layer to query |
| `analysis` | Derived results, always rebuildable from `core` |
| `h3` | Equal-area hex rollups at three resolutions |
| `serve` | Thin views; the only schema exposed to tile and feature servers |
| `meta` | Dataset registry, quality-control runs, lineage |

### Services

| Service | Port | Purpose |
| --- | --- | --- |
| PostGIS | 5432 | Authoritative database |
| pg_tileserv | 7800 | Vector tiles from SQL |
| pg_featureserv | 9000 | OGC API — Features |
| TiTiler | 8001 | Dynamic raster tiles from COGs |
| MinIO | 9001 | S3-compatible object store |

Full detail in [`docs/architecture.md`](docs/architecture.md).
Boundary reference: [`docs/boundaries.md`](docs/boundaries.md).

---

## Validation

No result is published until it has been checked in SQL. This is enforced in
three places rather than left to reviewers:

1. Every file in `db/analysis/` ends with a validation block reporting row
   counts, areas and extents.
2. `db/qc/checks.sql` runs coordinate-system, geometry, hierarchy,
   completeness, plausibility and licensing checks, writing every result to
   `meta.qc_result`. An error-level failure exits non-zero.
3. `pipelines/50_export.py` refuses to export from a build whose last QC run
   failed.

```bash
make qc
```

---

## Conventions

**Store in EPSG:4326, measure in EPSG:32630.** Ghana straddles the prime
meridian, so no UTM zone fits perfectly; zone 30N keeps scale error under
roughly 0.1% in the eastern strip, which is suitable for analysis but not for
cadastral survey. Use `core.gh_area_m2()` and the related helpers —
`ST_Area` on a 4326 geometry returns square degrees.
See [`docs/crs.md`](skills/ghana-geosql/references/crs.md).

**Apply both filters on a spatial join.** `&&` for the index gate, then
`ST_Intersects` for correctness.

**Nothing is publishable by default.** `meta.dataset.publishable` starts
false. Export refuses uncleared datasets, and QC fails a build where a
publishable dataset lacks an attribution string.

**Describe data accurately.** Observed surface water is not modelled flood
risk; straight-line distance is not travel time; modelled population is not a
census count.

Detailed guidance: [`AGENTS.md`](AGENTS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Using the agent skill

`ghana-geosql` teaches an agent this database: its schema, Ghana's place-name
ambiguities, the coordinate systems, and the validation required before any
result is presented.

```bash
cp -r skills/ghana-geosql ~/.claude/skills/
```

```
/ghana-geosql Map health facility access across the Upper West Region
/ghana-geosql Which districts have the most buildings on flood-prone land?
/ghana-geosql Compare road density between Ashanti and Northern
```

The skill discovers the schema, resolves place names against the database,
writes the SQL, runs the validation block and only then renders a map. Where
the data cannot answer a question, it says so rather than approximating.

Behavioural tests are in [`evals/evals.json`](evals/evals.json).

---

## Known limitations

- **No electricity grid layer.** Siting analysis uses road distance as a
  remoteness proxy.
- **No travel-time surface.** All accessibility figures are straight-line
  distance, which understates journeys during the rainy season.
- **No hydraulic flood model.** Flood exposure derives from observed
  historical surface water and terrain, without return periods or depths.
- **No cadastral or land-tenure data.**
- **Facility attributes are thin** — no bed counts, staffing or opening hours.
- **Population is modelled**, disaggregated from census totals rather than
  counted.

Planned work is listed in [`ROADMAP.md`](ROADMAP.md).

---

## Licence

Code is MIT licensed; see [`LICENSE`](LICENSE).

Data is not. Each dataset retains the licence of its producer, and several
restrict redistribution. Administrative boundaries are published as Common
Operational Datasets, normally under CC BY 3.0 IGO, with terms set per
dataset. Read [`LICENSE-DATA.md`](LICENSE-DATA.md) before publishing anything
derived from this platform.

Attribution required for the boundaries:

> Administrative boundaries: OCHA Ghana Common Operational Dataset (COD-AB)

---

## Acknowledgements

The pipeline architecture is adapted from
[rafimt/geospatial-data-pipeline](https://github.com/rafimt/geospatial-data-pipeline).
The agent workflow, and the practice of validating every result in SQL before
rendering, is adapted from
[dekart-xyz/geosql](https://github.com/dekart-xyz/geosql) (MIT).
Details in [`docs/migration-notes.md`](docs/migration-notes.md).
