# What was taken from where

This project is a deliberate migration of two existing repositories, retargeted
at Ghana. This file records what came from each, what changed and why, so that
credit is traceable and the decisions are reviewable.

## From rafimt/geospatial-data-pipeline

**Kept:**

- The numbered-step pipeline structure, which makes the order of operations
  obvious and each stage independently rerunnable
- The schema separation of raw, processed and analysis - renamed here to raw,
  core and analysis, with `h3`, `serve` and `meta` added
- Loading rasters by piping `raster2pgsql` into `psql`, including closing the
  parent's end of the pipe to avoid the deadlock
- The QC step as a distinct stage: CRS consistency, geometry validity,
  attribute completeness, raster value ranges
- The analysis vocabulary: buffers, overlays, raster sampling per polygon,
  DBSCAN clustering, nearest-neighbour distance, weighted suitability scoring

**Changed:**

| Original | Here | Why |
| --- | --- | --- |
| Hardcoded `C:\RMTPROJECTS\...` paths | `config/ghana.yml` and `pipelines/common/config.py` | Runs the same on a laptop, a server and in CI |
| Denver bbox, EPSG:32613 | Ghana bbox, EPSG:32630 with the meridian caveat documented | Different country, harder CRS problem |
| `CREATE TABLE AS` then a block of `UpdateGeometrySRID` calls | Load via `to_postgis`, declare typed geometry columns | The repair becomes unnecessary once the SRID is registered at write time |
| QC printed to the console | QC written to `meta.qc_result`, with a non-zero exit on error | A build gate rather than a scrollback buffer |
| Folium output | MapLibre viewer, vector tiles, OGC API, DuckDB-WASM | Shareable, queryable, does not require Python to view |
| `ee.Authenticate()` at module import | STAC over AWS and Planetary Computer, GEE optional | Removes an account requirement from the critical path |
| No licence tracking | `meta.dataset` with a `publishable` gate | Several Ghana-relevant sources have real restrictions |

## From dekart-xyz/geosql (MIT)

**Kept, nearly wholesale:**

- The five-step workflow: discover schema, resolve the target area, draft,
  validate, map
- The rule that validation happens in SQL and happens before the user sees
  anything
- The two-filter pattern: bbox gate for the index, exact predicate for
  correctness, with the overlap-not-containment warning
- Casting 64-bit integers before binding them to a visual channel
- The dialect-reference structure, so SKILL.md stays short
- The map styling rules: high density, multiple encoding channels, palette by
  data type, never rainbow
- Looking at the rendered map before claiming visual insight
- The eval suite as behavioural assertions rather than "did it answer"
- The Claude plugin manifest layout

**Changed:**

| Original | Here | Why |
| --- | --- | --- |
| Five engines (BigQuery, Snowflake, Wherobots, DuckDB, Postgres) | Two (PostGIS, DuckDB) | One country, one database, no warehouse bill |
| Dry-run cost gate for BigQuery | Plausibility gate against Ghana's real figures | No per-byte billing; the risk is a wrong answer, not an expensive one |
| Overture `division_area` for place resolution | `core.admin_region` and `core.admin_district`, with Ghana's name ambiguities documented | Accra means three different things, and 10 regions means a pre-2019 source |
| Dekart as the required map path | Built-in viewer first, Dekart optional | One fewer dependency for the common case |
| Generic geospatial reference | Ghana reference figures for sanity checks | A validation step needs something to validate against |
| - | Licence and sensitivity rules in the skill | The agent should not be the weak point in data governance |

## From opengeos/GeoLibre (MIT)

A browser-first GIS platform covering far more ground than this project needs.
Four things were worth taking:

| Taken | Why it mattered |
| --- | --- |
| **The spatial extension does load in DuckDB-WASM** | It is published for the WebAssembly platforms on the 1.33 line, and `INSTALL` and `LOAD` must be sent as separate statements. Sending them joined by a semicolon fails, which is exactly the bug that had left this viewer without any spatial capability |
| **Read-only SQL guard** | Mask literals, then require `SELECT`/`WITH` and reject side-effecting keywords anywhere in the statement, so a data-modifying CTE is caught rather than only a leading `DROP` |
| **Multiple model providers** | Anthropic, OpenAI, Google and any OpenAI-compatible endpoint, each with the reader's own key, rather than one hard-wired vendor |
| **Result export** | An answer that cannot leave the page is a demo |

A fifth followed once the first four were in: **vector geoprocessing in the
browser**, built on the same Turf library GeoLibre uses for its vector tools.
Buffer, dissolve, centroid, convex hull, simplify, Voronoi and measurement now
run in the page on features already downloaded.

A sixth followed the same principle GeoLibre is built on - that a browser can
stream open data directly, with no server in between. **Live layers** fetch
facilities, roads and buildings from the Overpass API for the current view and
register each result as a table, which fills the layers that would otherwise
sit empty for anyone without the pipeline.

Not taken:

- **The WebAssembly toolbox.** GeoLibre's 1,000-plus tools are WhiteboxTools
  compiled to WASI and shipped as the `geolibre-wasm` package - a 23 MB module
  run in a pooled worker over a virtual filesystem. It is public and could be
  loaded, but most of those tools are terrain, hydrology and LiDAR operations
  that need raster data in the browser, which this platform does not serve
  there. The machinery would arrive before the data it operates on.
- The Tauri desktop and mobile builds, planetary basemaps, the plugin
  architecture, and the collaborative editing layer - a different scale of
  project.

## The idea worth keeping from both

Row counts and areas validated in SQL before anything is drawn, and a rendered
map inspected before anything is claimed about it. That is what makes a map
trustworthy, and it is the reason this project exists in this shape rather
than as another collection of notebooks.
