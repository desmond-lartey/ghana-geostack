# What data exists, and what it actually means

Read this before answering a question about Ghana. Knowing what a column
measures matters more than knowing the SQL.

## Query the live catalogue first

```sql
SELECT id, title, theme, schema_name, table_name,
       feature_count, licence, publishable, updated_at
FROM meta.dataset ORDER BY theme, title;
```

`config/sources.yml` is the fuller catalogue, including sources not yet loaded.

## Core tables

| Table | What it is | Watch out for |
| --- | --- | --- |
| `core.admin_country` | National boundary | One row |
| `core.admin_region` | 16 regions, p-coded GH01–GH16 | A result containing Brong Ahafo is a superseded boundary set |
| `core.admin_district` | 260 MMDAs, p-coded GHrrdd | `assembly_type` is derived from the published name, not the legal instrument |
| `core.admin_alias` | Alternative and superseded names | Search resolves through this as well as the primary name |
| `core.gazetteer` | Flat searchable place list across all levels | Match on `place_norm` with trigram similarity, not equality |
| `core.building` | Footprints, partitioned by region | `confidence` is NULL for OSM and surveyed data, which is not the same as low confidence. Filter ML sources at ≥ 0.7 |
| `core.road` | Road network, OSM-derived | `class` is normalised: `primary` includes `primary_link`. OSM includes tracks and footpaths, so total length exceeds the classified network |
| `core.facility` | Health, education, market, water, energy, government points | Coverage is uneven. Absence of a facility in the data is not evidence of absence on the ground |
| `core.population_grid` | WorldPop 100 m cells | Modelled, not counted. Disaggregated from census totals, so it inherits census error and adds its own |
| `core.waterway` | Rivers, streams, canals, drains | OSM maps urban drains inconsistently. Length filters matter |
| `core.landcover` | ESA WorldCover classes | 10 m, single epoch |
| `core.dem`, `core.slope` | Copernicus GLO-30 raster | Voids over water. Values outside −10 to 1000 m indicate nodata read as data |

## Analysis tables and what they do not claim

| Table | Claims | Does not claim |
| --- | --- | --- |
| `analysis.building_access` | Straight-line distance to the nearest facility | Travel time. No road network routing, no terrain, no river crossings. Real journeys are longer, often much longer in the rainy season |
| `analysis.flood_prone_zone` | Land within 250 m of a watercourse and within 5 m of its bed elevation | Flood risk. No return period, no depth, no hydraulic model |
| `analysis.building_flood_exposure` | Buildings intersecting that zone | That those buildings will flood |
| `analysis.site_suitability` | A weighted score from visible weights | Objectivity. Change the weights, change the answer. The components are kept alongside the total so the ranking can be argued with |

When presenting any of these, state the limitation in the same breath as the
number. "2,084 buildings fall within the flood-prone zone" is fine. "2,084
buildings are at risk of flooding" is not, and the difference matters to
whoever reads it next.

## Licences, which are not a formality

| Source | Licence | Consequence |
| --- | --- | --- |
| OpenStreetMap | ODbL 1.0 | Share-alike. A published derived database must also be ODbL. Attribution required |
| Overture | ODbL / CDLA mixed | Varies by contributing source |
| Google Open Buildings | CC BY 4.0 | Attribution required |
| Ghana COD-AB | CC BY 3.0 IGO (confirm per dataset) | Attribution required. The authoritative boundary source |
| GADM | Non-commercial | Superseded by COD-AB. Retained as a fallback only |
| WorldPop, ESA WorldCover, GRID3 | CC BY 4.0 | Attribution required |
| Copernicus DEM | Copernicus licence | Attribution required |

`pipelines/50_export.py` refuses to export anything with `publishable = false`,
and QC fails a build where a publishable dataset has no attribution string.
That gate is deliberate, and working around it is not a shortcut, it is a
licence breach.

## Sensitivity

`meta.dataset.sensitivity` is `public`, `restricted` or `internal`. Restricted
covers anything that could identify a household or an individual service user.
Restricted data is never tiled at high zoom and never exported publicly, even
when the licence would allow it. Facility locations are public; anything
linking a person to a location is not.

## Gaps worth naming out loud

Rather than approximating, say the data is missing:

- **No electricity grid layer.** Mini-grid siting currently uses road distance
  as a remoteness proxy, which is a weaker signal. GRIDFINDER or ECG data would
  fix it.
- **No travel-time surface.** Everything is straight-line distance.
- **No engineered flood model.** Observed surface water is a proxy.
- **Facility attributes are thin.** No bed counts, staffing or opening hours.
- **No cadastral or land-tenure layer**, which is the single most requested
  thing in Ghanaian GIS and the hardest to obtain.
- **Agricultural data is seasonal and mostly absent.**
