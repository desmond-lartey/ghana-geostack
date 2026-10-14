# The Ghana data library

**Home → Ghana Data → Ghana Data Library.** One place that answers *what is
there for Ghana* - thirty-five layers as cards, each with a picture, a
sentence, where it came from, what licence it carries, and whether it can be
drawn right now.

---

## Why a wall of cards and not a tree

A tree of layer names is for finding a layer you can already name. Almost
nobody arrives knowing that there is a 1 km friction surface for West Africa,
or what it would be good for, and a tree will never tell them. A catalogue is
for finding out what exists.

The arrangement is Google Earth's data-layer picker, and it was borrowed for
the same reason the ribbon was borrowed from ArcGIS Pro: people have used it,
so it needs no explaining. Search at the top, two filters, a grid of cards,
several chosen at once, one **Add to map** at the bottom.

---

## Four states, and none of them hidden

Every card says what would happen if you pressed Add.

| | |
| --- | --- |
| **Ready** | It draws now. Fourteen of the thirty-five |
| **Needs Earth Engine** | Connect an Earth Engine account on the Data tab and it draws. Eight |
| **Needs the database** | Too large for the browser; it comes with the PostGIS deployment and the tile pyramid. Four |
| **Analysis, not yet built** | The product this platform is for, with the method named and the pipeline not yet written. Nine |

A catalogue that listed only what works today would be fourteen cards and
would say nothing about what the platform is for. One that pretended
everything worked would waste an afternoon each time. So the state is on the
card, and pressing **Add to map** on a mixed selection reports each one:
*4 added · 2 not yet available*, with the reason for each in the Log.

The nine unbuilt products are the same kind of invitation as the ribbon's open
slots - a named job with a named method, waiting for whoever needs it first.
**15-minute access to health care** is cost-distance over the walking friction
surface from every facility; **Population exposed to flooding** is the
observed surface-water record crossed with the 100 m population grid and
summarised by district. Neither is a research problem. Both are an afternoon
for someone with the data mounted.

---

## The two filters

**Theme** narrows to one of eleven: Administrative, Population, Health,
Education, Water, Transport, Agriculture, Climate, Hazard, Environment,
Energy. The themed buttons beside the library on the Home tab open it already
narrowed, so *Home → Ghana Data → Flood and fire* is one click to the four
hazard layers.

**Region** is the clip, not a second setting that could disagree with it.
Choosing Ashanti sets the clip to Ashanti, says so under the filters, and
everything added from that point is cut to it - which is what anyone would
expect of a filter that says *Ashanti* while they press Add. See
[Layers and clipping](layers-and-clipping.md).

---

## What is in it


### Administrative

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Regions | geoBoundaries CGAZ | CC-BY 4.0 | Ready |
| Districts | geoBoundaries CGAZ | CC-BY 4.0 | Ready |
| Administrative capitals | geoBoundaries | CC-BY 4.0 | Ready |
| Census enumeration areas | Ghana Statistical Service | check with GSS before republishing | Not built |

### Population

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Population, 100 m | WorldPop, University of Southampton | CC-BY 4.0 | Earth Engine |
| Built-up surface, 1975 to 2030 | European Commission JRC, GHSL | CC-BY 4.0 | Earth Engine |
| 2021 census, by district | Ghana Statistical Service, 2021 PHC | GSS terms | Database |

### Health

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Health facilities | OpenStreetMap | ODbL - share-alike | Ready |
| 15-minute access to health care | Malaria Atlas Project friction surface, Weiss et al. 2020 | CC-BY 4.0 | Not built |
| Travel time to the nearest hospital | Malaria Atlas Project, Ghana Health Service | CC-BY 4.0 | Not built |

### Education

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Schools | OpenStreetMap | ODbL - share-alike | Ready |
| Children beyond 30 minutes of a school | WorldPop, Ghana Education Service | CC-BY 4.0 | Not built |

### Water

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Water points | OpenStreetMap | ODbL - share-alike | Ready |
| Surface water, 1984 to 2021 | JRC Global Surface Water, Pekel et al. 2016 | CC-BY 4.0 | Earth Engine |
| Rivers and the Volta system | HydroSHEDS, OpenStreetMap | ODbL and HydroSHEDS terms | Database |

### Transport

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Roads | OpenStreetMap | ODbL - share-alike | Ready |
| National road network | OpenStreetMap, Ghana Highway Authority | ODbL - share-alike | Database |
| Markets | OpenStreetMap | ODbL - share-alike | Ready |
| Travel time to the nearest market | Malaria Atlas Project friction surface | CC-BY 4.0 | Not built |
| Buildings | OpenStreetMap | ODbL - share-alike | Ready |
| Open Buildings footprints | Google Open Buildings v3 | CC-BY 4.0 | Database |

### Agriculture

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Land cover, 10 m | ESA WorldCover v200 | CC-BY 4.0 | Earth Engine |
| Tree cover and forest loss | Hansen / UMD / Google / USGS / NASA | CC-BY 4.0 | Earth Engine |
| Vegetation index, 16-day | NASA EOSDIS GIBS, MODIS Terra NDVI | public domain | Ready |
| Agricultural landscape | Sentinel-2, to be segmented | Copernicus open licence | Not built |

### Climate

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Rainfall, daily and seasonal | CHIRPS, Climate Hazards Center, UC Santa Barbara | public domain | Earth Engine |
| Land surface temperature | NASA EOSDIS GIBS, MODIS Terra LST | public domain | Ready |
| Rainfall against the normal | CHIRPS | public domain | Not built |

### Hazard

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Population exposed to flooding | JRC Global Surface Water, WorldPop | CC-BY 4.0 | Not built |
| Active fire detections | NASA EOSDIS GIBS, MODIS Thermal Anomalies | public domain | Ready |
| Burned area, monthly | NASA MODIS MCD64A1 | public domain | Earth Engine |

### Environment

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Elevation and slope | Copernicus DEM, © DLR e.V. and Airbus DS | Copernicus DEM licence | Earth Engine |
| What the satellite saw today | NASA EOSDIS GIBS, MODIS Terra | public domain | Ready |

### Energy

| Layer | Source | Licence | State |
| --- | --- | --- | --- |
| Night lights | NASA EOSDIS GIBS, VIIRS Day Night Band | public domain | Ready |
| Electrification, by district | VIIRS annual composite, Ghana Statistical Service | public domain | Not built |

---

## The thumbnails are drawn, not photographed

Thirty-five screenshots is three megabytes and thirty-five things to redo
whenever the styling moves. Each thumbnail is instead a few hundred bytes of
SVG generated from the entry - scattered points for a point layer, a branching
network for roads, concentric rings for a travel-time surface, a classed grid
for a choropleth, bright points on black for night lights. Seeded from the
layer's id, so a card looks the same on every visit rather than reshuffling as
you scroll.

They say what kind of thing a layer is at a glance, which is their whole job.
They are not pictures of Ghana and are not meant to be mistaken for the data.

---

## Adding to it

One entry in the `LIBRARY` array in `web/index.html`:

```js
{
  id: "lib.soils", title: "Soil types", theme: "Agriculture",
  thumb: "landcover", tint: "#8C7D66", status: "database",
  blurb: "The national soil map, as mapped by CSIR-Soil Research Institute.",
  source: "CSIR-SRI", licence: "check before republishing"
}
```

A card appears, filtered and searchable, saying it needs the database. Give it
an `add` function and it says Ready and draws; give it `ee:` with an Earth
Engine collection id, or `catalog:` with the id of an entry in the earth
observation catalogue, and the library handles the rest.

`tests/library.cjs` holds the catalogue to its word: every entry carries a
source and a licence, and nothing may say **Ready** without a way to draw
itself.
