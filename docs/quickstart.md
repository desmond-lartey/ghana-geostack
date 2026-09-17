# Quick start

Three paths, depending on what you have. Pick one.

## 1. Just look at the data — five minutes, no install

Download `ghana.duckdb` and the GeoParquet files from the latest release, then:

```bash
duckdb ghana.duckdb
```

```sql
SELECT * FROM ghana.catalogue;            -- what is in here and who to credit

SELECT name, round(area_km2) AS km2, population
FROM ghana.region ORDER BY km2 DESC;

SELECT class, round(sum(length_m)/1000) AS km
FROM ghana.road GROUP BY 1 ORDER BY km DESC;
```

Everything works offline once downloaded. The Parquet files open in QGIS,
GeoPandas, R and ArcGIS Pro directly.

## 2. Run the whole stack — an hour, mostly downloading

```bash
git clone https://github.com/YOUR-ORG/ghana-geostack
cd ghana-geostack
cp .env.example .env

conda env create -f environment.yml
conda activate ghana-geostack

make up                  # PostGIS, tile server, feature server, TiTiler, MinIO
make pipeline            # fetch, load, analyse, validate, export
make serve               # http://localhost:8080/web/
```

`make pipeline` is `migrate fetch load analysis qc export` in order. Run the
stages individually if something fails; each is independently rerunnable.

### A faster first run

Ghana's full building set is large. To see the stack working in a few minutes:

```bash
make up && make migrate
make fetch-accra
make load analysis qc
make serve
```

## 3. Use it with Claude

```bash
cp -r skills/ghana-geosql ~/.claude/skills/
```

```
/ghana-geosql Which districts have the worst health facility access?
/ghana-geosql Map building density across Kumasi as hexes
/ghana-geosql How long is the trunk road network in the Northern Region?
```

## Troubleshooting

**`make up` hangs on the health check.** Port 5432 is probably taken by a
local PostgreSQL. Set `PGPORT=5433` in `.env`.

**`psql: command not found` during load.** The PostgreSQL client tools are not
on your PATH. `conda install postgresql`, or run rasters from inside the
container.

**Raster loading is skipped.** That is `raster2pgsql` missing. Vector analysis
still works; terrain and flood exposure do not.

**`ST_Value` errors about GDAL drivers.** Raster access is off:
`SET postgis.gdal_enabled_drivers = 'ENABLE_ALL';`

**QC fails on `region_count`.** Your boundary source has 10 regions, so it
predates 2019. GADM 4.1 is patchy on the new regions — this is a known gap,
see ROADMAP.

**Areas come out around 0.0001.** You measured in square degrees. Use
`core.gh_area_m2()`.

**The map shows only a basemap.** The layer binding is wrong. Check the
geometry column name, that the `serve` view exists, and that pg_tileserv can
see it. `curl http://localhost:7800/index.json` lists what it is publishing.

**`make export` refuses to run.** The last QC run failed. That is the gate
working. Fix the errors it reported and re-run `make qc`.
