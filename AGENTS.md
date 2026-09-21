# AGENTS.md — instructions for coding agents working in this repo

## Skills

- **ghana-geosql** — spatial SQL against the Ghana GeoStack, with mandatory
  validation before any result is presented. File: `skills/ghana-geosql/SKILL.md`.

Load it when the request involves querying, mapping or analysing Ghanaian
spatial data. Read the matching dialect reference in
`skills/ghana-geosql/references/` as well; the SKILL.md is deliberately short
and the detail lives there.

## Rules that apply to any change in this repo

1. **Constants live in `config/ghana.yml`.** No hardcoded bbox, SRID, region
   list or file path in a script. If you need a new constant, add it there.
2. **A new data source starts in `config/sources.yml`**, with its licence and
   attribution filled in, before any code fetches it.
3. **Measure in metres.** `ST_Area` and `ST_Length` on 4326 geometry return
   degrees. Use the `core.gh_*` helpers.
4. **Both filters on a spatial join**: `&&` for the index gate, `ST_Intersects`
   for correctness.
5. **Join administrative units on p-codes, never on names.** A district's
   parent region is `left(id, 4)`.
6. **Every load ends with validation and registration.** `check_table()`, then
   `db.register()`. An unregistered table fails QC.
7. **`publishable` defaults to false.** Flip it only after reading the licence.
8. **Analysis SQL is idempotent.** Drop and rebuild its own tables, end with a
   validation block, and be safe to run twice.
9. **Say what the data is.** Observed surface water is not modelled flood risk.
   Straight-line distance is not travel time.

## Layout

```
config/      constants and the data catalogue
db/          migrations, raw-to-core transforms, analysis, QC
pipelines/   numbered Python steps; common/ holds shared helpers
duckdb/      server-free query path
skills/      the agent skill and its references
web/         the browser viewer
docs/        longer-form documentation
```

## Before opening a pull request

```bash
make lint
make qc
```

QC failing means the build does not get published. That is the intended
behaviour, not an obstacle to route around.
