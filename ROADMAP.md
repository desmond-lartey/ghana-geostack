# Roadmap

Ordered by what unblocks the most, not by what is most interesting to build.

## Complete

- [x] **Authoritative boundaries.** Ghana COD-AB v01, valid from 8 March 2021:
      16 regions, 260 districts, 177 capitals, p-coded at every level and
      openly licensed.
- [x] Vintage-aware boundary schema with archive tables and a lineage
      crosswalk covering the 2019 reorganisation.
- [x] Dependency-free shapefile converter, so boundaries load without GDAL.

## Now

- [ ] Load the full national building set (Google Open Buildings v3 plus
      Overture) and validate the count against known figures.
- [ ] Load WorldPop and join population to districts.
- [ ] Load health and education facilities, and reconcile healthsites.io
      against any Ghana Health Service list we can obtain.
- [ ] First public export: GeoParquet, the DuckDB file, and PMTiles, with
      attribution.

## Next — make it useful

- [ ] **Travel-time surface.** Straight-line distance understates real
      journeys badly, especially in the rainy season. Either pgRouting over
      the OSM network or an isochrone service. This improves every
      accessibility number in the stack.
- [ ] **Electricity grid layer.** GRIDFINDER, ECG or Energy Commission data,
      which would replace the road-distance proxy in the siting analysis.
- [ ] Seasonal flood extent from Sentinel-1 SAR, which sees through cloud —
      relevant given Ghana's rainy season is also its cloudy season.
- [ ] Agricultural layers: CHIRPS rainfall, cropland masks, growing-season
      NDVI.
- [ ] STAC catalogue for the raster holdings, served alongside TiTiler.
- [ ] Time dimension: keep historical snapshots so change can be measured
      rather than inferred.

## Later — make it shared

- [ ] Public read-only API with rate limiting.
- [ ] Hosted viewer on a stable URL, with the exports behind a CDN.
- [ ] Data request and contribution workflow for institutions.
- [ ] Twi, Ewe and Ga place-name aliases in the name-matching table.
- [ ] Offline field package: PMTiles plus the DuckDB file on a phone, for
      areas where connectivity is the binding constraint.
- [ ] Partnership conversations with Ghana Statistical Service, the Lands
      Commission, university geography and planning departments, and the
      OpenStreetMap Ghana community.

## Ongoing

- [ ] Expand the QC suite every time something is found to be wrong. A bug
      that reaches a map should leave a check behind it.
- [ ] Expand `evals/evals.json` as the skill's failure modes become clear.
- [ ] Keep `data-catalog.md` honest about what each layer does not measure.

## Deliberately not doing

- **Not building another portal.** There are several; the problem is not a
  shortage of download links.
- **Not a cadastral system.** Land tenure in Ghana is legally and politically
  complex, and a map that looks authoritative about plot boundaries would do
  real harm. The stack should support land administration work, not pretend to
  be it.
- **Not hiding uncertainty behind a nice interface.** Where the data is thin,
  the output says so.
