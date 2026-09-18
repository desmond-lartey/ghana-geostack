# Ghana GeoStack

**Open spatial data infrastructure for Ghana.**

<div class="badges" markdown>
![status](https://img.shields.io/badge/status-active-2EA043)
![code](https://img.shields.io/badge/code-MIT-informational)
![boundaries](https://img.shields.io/badge/boundaries-CC%20BY%203.0%20IGO-blue)
![regions](https://img.shields.io/badge/regions-16-F2683C)
![districts](https://img.shields.io/badge/districts-260-F2683C)
![source](https://img.shields.io/badge/COD--AB-v01%20%C2%B7%202021-6E7B8B)
</div>

PostGIS as the authoritative store, DuckDB for portable analysis, GeoParquet
for interchange, vector tiles and an OGC API for the web. Administrative
boundaries for all 16 regions and 260 districts ship with the repository, so a
clone is immediately useful.

The live map is at [ghana-geostack.vercel.app](https://ghana-geostack.vercel.app),
and the source at [github.com/desmond-lartey/ghana-geostack](https://github.com/desmond-lartey/ghana-geostack).

## What this platform does

- **Consolidates Ghana's spatial data** into one database with one coordinate
  system, one catalogue and one set of conventions, rather than a dozen portals
  in a dozen formats.
- **Ships the administrative boundaries** - 16 regions, 260 districts and 177
  capitals from the Ghana Common Operational Dataset, p-coded at every level and
  openly licensed.
- **Validates every result in SQL** before it is published. Row counts, areas,
  coordinate systems, hierarchy and licensing are all checked, and a failing
  check stops the build.
- **Runs without a server.** The same data is published as GeoParquet and as a
  single DuckDB file, so analysis works on a laptop, offline, with no
  installation beyond DuckDB itself.
- **Serves the web directly** through vector tiles, an OGC API and a browser map
  that queries the data in place using DuckDB compiled to WebAssembly.
- **Teaches an assistant the schema** through a packaged agent skill covering
  Ghana's place-name ambiguities, the coordinate systems, and the validation
  required before any map is drawn.

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

The full catalogue, with licences, is in [Data catalogue](skill/data-catalog.md).

## Included analyses

- **Accessibility.** Distance from every building to the nearest health or
  education facility, summarised by district against the 5 km catchment Ghana
  Health Service plans CHPS compounds around.
- **Flood exposure.** Buildings on low ground near watercourses, derived from
  observed historical surface water and terrain.
- **Building density.** Hex-grid rollups at national, regional and urban
  resolution, on equal-area cells rather than districts.
- **Siting suitability.** Weighted multi-criteria scoring, with the weights held
  in a visible table and component scores retained beside the total.

## Getting started

Boundaries only, with nothing installed: the GeoJSON files in `data/reference/`
open directly in QGIS, or in a few lines of Python. The full dataset with no
database runs from the published DuckDB file. The whole stack, with PostGIS and
a tile server, is three commands. All three paths are set out in
[Quick start](quickstart.md).

Deploying your own copy, with the map on Vercel and the documentation on GitHub
Pages, is covered in [Deployment](deployment.md).

## Conventions

!!! warning "Measure in metres, store in degrees"

    Ghana straddles the prime meridian, so no UTM zone fits perfectly. Data is
    stored in EPSG:4326 and measured in EPSG:32630, which keeps scale error
    under roughly 0.1% in the eastern strip. `ST_Area` on a 4326 geometry
    returns square degrees, so use `core.gh_area_m2()` instead. See
    [Coordinate systems](skill/crs.md).

!!! info "Join on p-codes, never on names"

    Every administrative unit carries an OCHA place code, and the hierarchy is
    encoded in it: `GH07` is Greater Accra and `GH0701` a district within it. A
    district's parent is `left(id, 4)`. See
    [Administrative boundaries](boundaries.md).

!!! danger "Nothing is publishable by default"

    `meta.dataset.publishable` starts false. Export refuses uncleared datasets,
    and quality control fails a build where a publishable dataset lacks an
    attribution string. See [Data licensing](project/licensing.md).

## Known limitations

- No electricity grid layer, so siting analysis uses road distance as a
  remoteness proxy.
- No travel-time surface. All accessibility figures are straight-line distance,
  which understates journeys during the rainy season.
- No hydraulic flood model. Exposure derives from observed surface water and
  terrain, and carries no return period or depth.
- No cadastral or land-tenure data.
- Facility attributes are thin - no bed counts, staffing or opening hours.
- Population is modelled from census totals rather than counted.

Planned work is listed in the [Roadmap](project/roadmap.md).

## Licence

Code is MIT licensed. Data is not - each dataset retains the licence of its
producer, and several restrict redistribution. Read
[Data licensing](project/licensing.md) before publishing anything derived from
this platform.

Boundaries require attribution:

> Administrative boundaries: OCHA Ghana Common Operational Dataset (COD-AB)
