# Data licensing

**The MIT licence on this repository covers the code. It does not cover the
data.** Each dataset keeps the licence of whoever produced it, and several of
those licences restrict what you may do with the result.

Read this before publishing a map, a tileset, an export or an analysis.

## The obligations, by licence

### ODbL 1.0 — OpenStreetMap, Overture (in part), Microsoft footprints, healthsites.io

Share-alike. If you publish a **derived database** — a modified version, a
subset, an extract, a database built from it — you must publish it under ODbL
too. Producing a map image from it is a "produced work" and only requires
attribution, not share-alike.

Required credit: `© OpenStreetMap contributors, ODbL`

Practical consequence for this project: OSM-derived tables are tagged with
`source_id = 'osm_ghana'` so that exports can be separated. Do not silently
merge ODbL data into a layer you intend to license differently.

### CC BY 4.0 — Google Open Buildings, WorldPop, ESA WorldCover, GRID3, JRC

Attribution required, and the credit must be reasonably visible. No
share-alike, so a derived product may carry a different licence, but the
credit travels with it.

### GADM — non-commercial only

**GADM boundaries may not be used commercially and may not be redistributed.**
They are loaded here with `publishable = false` and the export step will
refuse them. They exist so the stack runs on day one, and should be replaced
by Ghana Statistical Service or GRID3 boundaries before any public release.

### Copernicus DEM

Free to use with attribution:
`© DLR e.V. 2010-2014, © Airbus Defence and Space GmbH`

### Ghana Statistical Service, Ghana Open Data Initiative, HDX

Varies per dataset, and often unstated. Record the actual licence in
`meta.dataset` when you load it. Do not assume government publication implies
open licensing.

## How this is enforced

Not by good intentions:

1. `meta.dataset.publishable` defaults to **false**. A dataset is only
   publishable once someone has read its licence and set the flag.
2. `pipelines/50_export.py` exports only publishable datasets and will not
   run at all if the last QC run failed.
3. `db/qc/checks.sql` fails the build if a publishable dataset has no
   attribution string.
4. Every export writes `attribution.md` listing the credit for each layer.

Working around these checks to ship faster is a licence breach, not a
shortcut.

## Attribution on maps

Every published map must carry, visibly:

- what is shown and for when
- the credit line from `meta.dataset.attribution` for each layer used
- the extraction date

## Privacy

`meta.dataset.sensitivity` marks data as `public`, `restricted` or `internal`.

Restricted covers anything that could identify a household or an individual
service user. Restricted data is never tiled at high zoom and never exported
publicly, **even where the licence would permit it.** Facility locations are
public information. Anything linking a person to a location is not, and an
open licence does not make it so.
