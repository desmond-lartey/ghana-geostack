# Administrative boundaries

## Source

Ghana Common Operational Dataset - administrative boundaries (COD-AB),
version v01, valid from 8 March 2021. Published via the Humanitarian Data
Exchange at https://data.humdata.org/dataset/cod-ab-gha

Common Operational Datasets are the reference boundaries used for
humanitarian coordination in a country, maintained in cooperation with the
national statistical authority. They are the appropriate boundary source for
analysis intended to be comparable with official statistics.

**Licence.** Common Operational Datasets are normally released under
CC BY 3.0 IGO, but terms are set per dataset. Confirm on the dataset page
before redistributing.

**Attribution.**

> Administrative boundaries: OCHA Ghana Common Operational Dataset (COD-AB)

## Contents

| Layer | Features | Geometry | Committed as |
| --- | --- | --- | --- |
| `gha_admin0` | 1 | Polygon | `data/reference/gha_admin0.geojson` |
| `gha_admin1` | 16 | Polygon | `data/reference/gha_admin1.geojson` |
| `gha_admin2` | 260 | Polygon, MultiPolygon | `data/reference/gha_admin2.geojson` |
| `gha_admincapitals` | 177 | Point | `data/reference/gha_admincapitals.geojson` |

The original bundle also contains `gha_adminlines` (boundary lines, including
disputed segments), `gha_adminpoints` (277 settlement points) and `_em`
variants carrying extended maritime extent. These are not converted by
default; add them to the layer list in `pipelines/01_fetch_admin.py` if
needed.

Coordinate reference system: geographic WGS 84 (EPSG:4326).

Extent: −3.2621 to 1.2003 longitude, 4.7407 to 11.1747 latitude.

## P-codes

Place codes are the join key throughout this database. They are stable across
releases and independent of spelling, and the hierarchy is encoded in the code
itself.

| Level | Pattern | Example |
| --- | --- | --- |
| Country | `GH` | `GH` |
| Region | `GH` + 2 digits | `GH07` Greater Accra |
| District | region code + 2 digits | `GH0701` Ablekuma Central Municipal |

A district's parent region is `left(id, 4)`. Resolving the hierarchy therefore
requires no spatial join, which removes the error class where a district is
attributed to the wrong region because its representative point fell outside a
concave boundary.

### Region codes

| Code | Region | Capital | Area km² | Districts |
| --- | --- | --- | ---: | ---: |
| GH01 | Ahafo | Goaso | 5,195 | 6 |
| GH02 | Ashanti | Kumasi | 24,379 | 43 |
| GH03 | Bono | Sunyani | 11,647 | 12 |
| GH04 | Bono East | Techiman | 23,256 | 11 |
| GH05 | Central | Cape Coast | 9,664 | 22 |
| GH06 | Eastern | Koforidua | 18,966 | 33 |
| GH07 | Greater Accra | Accra | 3,699 | 29 |
| GH08 | Northern | Tamale | 24,849 | 16 |
| GH09 | North East | Nalerigu | 9,075 | 6 |
| GH10 | Oti | Dambai | 11,066 | 8 |
| GH11 | Savannah | Damongo | 35,863 | 7 |
| GH12 | Upper East | Bolgatanga | 8,622 | 15 |
| GH13 | Upper West | Wa | 19,033 | 11 |
| GH14 | Volta | Ho | 9,825 | 18 |
| GH15 | Western | Sekondi-Takoradi | 14,258 | 14 |
| GH16 | Western North | Sefwi Wiawso | 10,075 | 9 |

Total: 239,473 km², identical at region and district level.

This is about 0.4% above the commonly cited land area of 238,533 km², because
the boundary set includes coastal and inland water extent. QC checks against
the boundary figure, not the land-area figure.

## Known issues in the source

**"Northern East".** The source spells the North East Region as
"Northern East". `db/transform/admin.sql` corrects this to the official name
and records the source spelling in `core.admin_alias`, so either form
resolves in search.

**Assembly type.** Districts are classified as metropolitan, municipal or
district assemblies. The distinction is derived from the published name, which
yields 6 metropolitan, 65 municipal and 189 district. The legal classification
comes from the instrument creating each assembly and is not consistently
reflected in the name, so `core.admin_district.assembly_type` is a working
default rather than an authority.

## Versioning

Ghana's administrative geography changed in 2012 and again in 2019. The schema
treats a boundary set as a dated version rather than a permanent fact.

| Table | Contents |
| --- | --- |
| `core.admin_region`, `core.admin_district` | The current set |
| `core.admin_region_archive`, `core.admin_district_archive` | Superseded sets |
| `core.admin_region_lineage` | Predecessor-to-successor crosswalk |
| `core.admin_alias` | Alternative and historical names |

Loading a newer release:

```sql
SELECT * FROM core.archive_admin();   -- move the current set to the archive
```

```bash
python pipelines/01_fetch_admin.py --shapefiles path/to/new_bundle
python pipelines/20_load_postgis.py --only admin
make qc
```

### The 2019 reorganisation

Six regions were created following referendums held on 27 December 2018,
formalised by constitutional instrument in February 2019.

| Predecessor | Successors |
| --- | --- |
| Brong Ahafo | Bono, Bono East, Ahafo |
| Northern | Northern, Savannah, North East |
| Volta | Volta, Oti |
| Western | Western, Western North |

`core.admin_region_lineage` records these. A split is not an apportionment: a
value recorded for Brong Ahafo cannot be divided between its three successors
without an explicit assumption about distribution. The `share_hint` column
records what that assumption should be based on - population or area - rather
than supplying a ratio.

## Converting an updated release

`pipelines/tools/shp2geojson.py` reads shapefiles without GDAL, GeoPandas or
pyshp, so boundaries can be loaded before the geospatial environment is
complete.

```bash
python pipelines/tools/shp2geojson.py path/to/*.shp --outdir data/reference
```

It reads the `.prj` and rejects projected input, reassembles shapefile ring
winding into RFC 7946 polygons and multipolygons, and verifies that the
attribute and geometry record counts match.

Verification after conversion:

```bash
python pipelines/01_fetch_admin.py --verify
```

This checks feature counts against the expected 1/16/260, confirms every
district p-code has a matching region, confirms geometry falls inside Ghana,
and confirms region and district areas agree to within 1 km².
