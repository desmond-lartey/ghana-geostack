# Contributing

## Setting up

```bash
git clone https://github.com/desmond-lartey/ghana-geostack
cd ghana-geostack
cp .env.example .env

# conda handles the GDAL stack far better than pip does
conda env create -f environment.yml
conda activate ghana-geostack

make up
make migrate
```

If you are on pip rather than conda, install GDAL first and everything else
after it. The C-extension packages (`pyproj`, `shapely`, `fiona`, `rasterio`)
must come before `geopandas`, and getting the order wrong produces library
errors that look like something else entirely.

## Adding a data source

In this order, no steps skipped:

1. **Add it to `config/sources.yml`** with its licence, attribution string and
   status. If you cannot fill in the licence, the source is not ready to add.
2. **Write the fetch step** in `pipelines/`, or extend an existing one.
   Validate the result with `check_gdf()` before it is written to disk.
3. **Write the raw-to-core transform** in `db/transform/`. Conform names,
   attach `district_id` and `region_id`, clean geometry with `core.gh_clean()`.
4. **Register it** with `db.register(...)` at the end of the loader.
   `publishable = False` unless you have read the licence and it permits it.
5. **Add a QC check** in `db/qc/checks.sql` for whatever would make this
   dataset wrong in a way the generic checks miss.
6. **Document it** in `skills/ghana-geosql/references/data-catalog.md`,
   including what it does *not* measure.

## Adding an analysis

Put it in `db/analysis/` as a numbered `.sql` file. It must:

- drop and recreate its own tables, so it is safe to run twice
- be rebuildable from `core` alone
- end with a validation block that prints counts and magnitudes
- state, in a comment at the top, what the output does not claim

That last one is not a nicety. An analysis file is where a proxy quietly
becomes a fact, and the comment is the only thing standing between "buildings
within 250 m of a watercourse on low ground" and "buildings at risk of
flooding".

## Code conventions

- **No hardcoded constants.** Bbox, SRID, region names and paths come from
  `config/ghana.yml`.
- **Measure in metres.** Use the `core.gh_*` helpers.
- **Both filters on a spatial join**: `&&` then `ST_Intersects`.
- **Type your geometry columns**: `geometry(MultiPolygon, 4326)`, so a bad
  insert fails at write time rather than producing a map of the Atlantic.
- **`ANALYZE` after a bulk load**, or the planner will ignore your index.
- Python is formatted with `ruff`. Run `make lint` before opening a PR.

## Before you open a pull request

```bash
make lint
make qc
```

A failing QC run is a blocking failure. If a check is wrong, fix the check and
say why in the PR; do not lower the threshold to make it pass.

## Data contributions

Data itself does not go in the repository. `data/` is gitignored and exports
are published as release artefacts. If you have data to contribute, open an
issue describing the source, its licence and its coverage, and we will add it
to the catalogue.

## Things we would particularly welcome

- Ghana Statistical Service boundaries, with permission to redistribute
- An electricity grid or transmission line layer
- A travel-time surface, which would improve every accessibility analysis here
- Verification of the Ghana National Grid parameters against the Lands
  Commission Survey and Mapping Division
- Place-name spelling variants for `db/transform/admin.sql`
- Anyone who knows the data well telling us where our numbers are wrong
