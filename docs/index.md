# Ghana GeoStack

**Open spatial data infrastructure for Ghana.**

<div class="badges" markdown>
![status](https://img.shields.io/badge/status-active-2EA043)
![licence](https://img.shields.io/badge/code-MIT-informational)
![data](https://img.shields.io/badge/boundaries-CC%20BY%203.0%20IGO-blue)
![regions](https://img.shields.io/badge/regions-16-F2683C)
![districts](https://img.shields.io/badge/districts-260-F2683C)
![boundaries](https://img.shields.io/badge/COD--AB-v01%20%C2%B7%202021-6E7B8B)
![engines](https://img.shields.io/badge/PostGIS%20%C2%B7%20DuckDB-GeoParquet-3E8E7E)
</div>

PostGIS as the authoritative store, DuckDB for portable analysis, GeoParquet
for interchange, vector tiles and an OGC API for the web. Administrative
boundaries for all 16 regions and 260 districts ship with the repository, so a
clone is immediately useful.

[Open the map](https://ghana-geostack.vercel.app){ .md-button .md-button--primary }
[Quick start](quickstart.md){ .md-button }

<div class="gh-grid" markdown>

<div class="gh-card" markdown>
#### Boundaries
16 regions, 260 districts, 177 capitals, p-coded at every level and openly
licensed.
</div>

<div class="gh-card" markdown>
#### Two engines
PostGIS for the authoritative database; DuckDB for analysis with no server,
including in the browser.
</div>

<div class="gh-card" markdown>
#### Validated
Row counts, areas, coordinate systems and licences checked in SQL before
anything is published.
</div>

<div class="gh-card" markdown>
#### Agent-ready
A skill that teaches an assistant this schema, Ghana's naming traps and the
validation it must perform.
</div>

</div>

## What it holds

| Theme | Layers | Source |
| --- | --- | --- |
| Administrative | 16 regions, 260 districts, 177 capitals | Ghana COD-AB |
| Buildings | Footprints with height, class, confidence | Overture, Google Open Buildings, OSM |
| Transport | Classified road network | OpenStreetMap |
| Population | 100 m gridded population | WorldPop |
| Facilities | Health, education, market, water, energy | healthsites.io, OSM |
| Terrain | 30 m elevation and slope | Copernicus DEM GLO-30 |
| Land cover | 10 m classes | ESA WorldCover |
| Hydrology | Rivers, streams, surface water | OSM, HydroSHEDS, JRC |

Full catalogue with licences: [Data catalogue](skill/data-catalog.md).

## Included analyses

- **Accessibility** — distance from every building to the nearest health or
  education facility, summarised by district against the 5 km CHPS catchment
- **Flood exposure** — buildings on low ground near watercourses, from observed
  historical surface water and terrain
- **Building density** — H3 hex rollups at national, regional and urban
  resolution
- **Siting suitability** — weighted multi-criteria scoring with visible weights

## Start here

<div class="gh-grid" markdown>

<div class="gh-card" markdown>
#### Just the data
Boundaries as GeoJSON, or the whole database as one DuckDB file.
[Quick start →](quickstart.md)
</div>

<div class="gh-card" markdown>
#### Run the stack
Docker, PostGIS, tile server and pipeline in three commands.
[Quick start →](quickstart.md)
</div>

<div class="gh-card" markdown>
#### Deploy it
Static map on Vercel, documentation on GitHub Pages.
[Deployment →](deployment.md)
</div>

<div class="gh-card" markdown>
#### Understand it
Schemas, data flow and the validation loop.
[Architecture →](architecture.md)
</div>

</div>

## Conventions

!!! warning "Measure in metres, store in degrees"

    Ghana straddles the prime meridian, so no UTM zone fits perfectly. Data is
    stored in EPSG:4326 and measured in EPSG:32630, which keeps scale error
    under roughly 0.1% in the eastern strip. `ST_Area` on a 4326 geometry
    returns square degrees — use `core.gh_area_m2()`.
    See [Coordinate systems](skill/crs.md).

!!! info "Join on p-codes, never on names"

    Every administrative unit carries an OCHA place code, and the hierarchy is
    encoded in it: `GH07` is Greater Accra, `GH0701` a district within it. A
    district's parent is `left(id, 4)`.
    See [Administrative boundaries](boundaries.md).

!!! danger "Nothing is publishable by default"

    `meta.dataset.publishable` starts false. Export refuses uncleared
    datasets, and quality control fails a build where a publishable dataset
    lacks an attribution string.
    See [Data licensing](project/licensing.md).

## Known limitations

- No electricity grid layer; siting analysis uses road distance as a proxy
- No travel-time surface, so accessibility figures are straight-line distance
- No hydraulic flood model; exposure derives from observed surface water
- No cadastral or land-tenure data
- Population is modelled from census totals rather than counted

Planned work: [Roadmap](project/roadmap.md).

## Licence

Code is MIT licensed. Data is not — each dataset retains the licence of its
producer, and several restrict redistribution. Read
[Data licensing](project/licensing.md) before publishing anything derived from
this platform.

Boundaries require attribution:

> Administrative boundaries: OCHA Ghana Common Operational Dataset (COD-AB)
