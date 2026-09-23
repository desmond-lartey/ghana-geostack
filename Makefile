# Ghana GeoStack
#
# Every stage is one command. `make help` lists them.
# The full path from nothing to a working map: make up && make pipeline && make serve

SHELL       := /bin/bash
COMPOSE     := docker compose -f docker/docker-compose.yml
PY          := python
PSQL        := psql -h $${PGHOST:-localhost} -p $${PGPORT:-5432} -U $${PGUSER:-ghana} -d $${PGDATABASE:-ghana} -v ON_ERROR_STOP=1

.DEFAULT_GOAL := help
.PHONY: help up down logs ps psql migrate fetch load analysis qc export pipeline serve duck \
        web icons docs docs-serve docs-build lint test clean reset

help:  ## List the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	 | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ────────────────────────────────────────────────────────

up:  ## Start PostGIS, tile server, feature server, TiTiler and MinIO
	$(COMPOSE) up -d
	@echo "Waiting for PostGIS to accept connections..."
	@until $(COMPOSE) exec -T postgis pg_isready -U $${PGUSER:-ghana} >/dev/null 2>&1; \
	 do sleep 1; done
	@echo "  postgis      localhost:$${PGPORT:-5432}"
	@echo "  tiles        http://localhost:7800"
	@echo "  features     http://localhost:9000"
	@echo "  rasters      http://localhost:8001"
	@echo "  object store http://localhost:9001"

down:  ## Stop the stack, keeping data
	$(COMPOSE) down

logs:  ## Follow container logs
	$(COMPOSE) logs -f

ps:  ## Show container status
	$(COMPOSE) ps

psql:  ## Open a psql shell
	@$(PSQL)

# ── Data pipeline ─────────────────────────────────────────────────────────

migrate:  ## Create schemas, tables, functions and views
	$(PY) pipelines/20_load_postgis.py --migrate

fetch:  ## Download source data (admin, OSM, Overture)
	$(PY) pipelines/01_fetch_admin.py
	$(PY) pipelines/02_fetch_osm.py
	$(PY) pipelines/03_fetch_overture.py --theme buildings

fetch-accra:  ## Fetch a single-city subset, for a fast first run
	$(PY) pipelines/01_fetch_admin.py
	$(PY) pipelines/03_fetch_overture.py --theme buildings --city accra
	$(PY) pipelines/03_fetch_overture.py --theme places --city accra

load:  ## Load into PostGIS, with validation
	$(PY) pipelines/20_load_postgis.py

analysis:  ## Run the spatial analysis SQL
	$(PY) pipelines/30_run_analysis.py

qc:  ## Run quality control; non-zero exit on any error-level failure
	$(PY) pipelines/40_qc.py

export:  ## Export GeoParquet, the DuckDB file, PMTiles and attribution
	$(PY) pipelines/50_export.py

pipeline: migrate fetch load analysis qc export  ## The whole thing, end to end
	@echo "Pipeline complete. Run 'make serve' to look at it."

# ── Serving and querying ──────────────────────────────────────────────────

serve:  ## Serve the web viewer at http://localhost:8080
	@echo "http://localhost:8080/web/"
	@$(PY) -m http.server 8080

duck:  ## Open DuckDB with the Ghana views loaded, no server needed
	duckdb -init duckdb/bootstrap.sql

# ── Publishing ────────────────────────────────────────────────────────────

web:  ## Build the static site into public/, as Vercel does
	$(PY) scripts/build_web.py

web-preview: web  ## Build the static site and serve it
	@echo "http://localhost:8080"
	@cd public && $(PY) -m http.server 8080

icons:  ## Regenerate the favicon and logo from the national boundary
	$(PY) scripts/make_icons.py

docs:  ## Sync the generated documentation pages
	$(PY) scripts/sync_docs.py

docs-serve: docs  ## Serve the documentation at http://localhost:8000
	mkdocs serve

docs-build: docs  ## Build the documentation site into site/
	mkdocs build --strict

# ── Development ───────────────────────────────────────────────────────────

# `ruff format` is offered as `make format` but is not enforced. Several files
# align columns deliberately — the zonal statistics tables, the catalogue field
# list — and a blanket reformat destroys that alignment for no gain.
lint:  ## Check Python style and SQL formatting
	ruff check pipelines/ scripts/
	@command -v sqlfluff >/dev/null && sqlfluff lint db/ --dialect postgres || \
	 echo "sqlfluff not installed, skipping SQL lint"

format:  ## Apply the automatic fixes ruff can make safely
	ruff check pipelines/ scripts/ --fix

test:  ## Run the test suite
	pytest -q tests/
	@command -v node >/dev/null && { $(MAKE) -s web >/dev/null && \
	  node tests/smoke_viewer.cjs && node tests/ee_clip.cjs; } || \
	 echo "node not installed, skipping the browser tests"

# ── Housekeeping ──────────────────────────────────────────────────────────

clean:  ## Remove downloaded data and build outputs, keeping exports
	rm -rf data/raw/* data/interim/*
	rm -rf public/ site/ docs/skill/ docs/project/
	@echo "Cleared raw data and build outputs. Exports and reference boundaries kept."

reset:  ## Destroy the database volume and start over. Irreversible.
	@read -p "This deletes the database and all loaded data. Type yes to continue: " ok; \
	 [ "$$ok" = "yes" ] || { echo "Cancelled."; exit 1; }
	$(COMPOSE) down -v
	@echo "Volumes removed. Run 'make up && make pipeline' to rebuild."
