# Layers and clipping

Two things that were missing and are related: knowing what is on the map, and
deciding what an analysis covers.

---

## The layer stack

Everything this session puts on the map is a card in the left dock, newest at
the top — Earth Engine rasters, live OpenStreetMap fetches, query results, tool
output, catalogue layers. What each card can do is described in
[The map interface](interface.md).

Before this, each producer drew into its own fixed layer ids and could only be
replaced, never managed. There was no way to see what was on the map, let alone
turn one thing off.

The design is GeoLibre's, because GeoLibre's is right. What differs is
underneath: a producer registers its layer once, with a label, its layer ids,
an extent, a colour and a legend if it has one, and everything else follows —
the card, the legend entry, the search result, the toolbox input. A new kind of
output is managed for free rather than needing controls of its own.

---

## Clipping

Set the clip from **Processing → Clip results to…**, or by clicking what the
status bar says it is currently set to. Every tool and every live fetch respects
it. The options are the whole country, the current view, any region or any
district.

This comes from the hotspots notebook, where one line does the work:

```python
gdf_poi = gpd.overlay(gdf_poi, admin[['geometry']])
```

The points are clipped to the city boundary *before* anything is clustered, and
that ordering is the point. Overpass answers a bounding box, which almost never
matches the place anyone had in mind, and an analysis run over whatever
happened to be fetched answers a question about the fetch rather than about the
place. A buffer that spills into Togo, a convex hull drawn around the whole
country, a Voronoi diagram tiling the Atlantic — the same mistake three times,
and clipping is the same fix.

What clipping does to each kind of geometry:

- **Points** are kept or dropped by a point-in-polygon test.
- **Polygons** are cut at the boundary, and keep their attributes — Turf's
  intersect discards them, so they are re-attached deliberately.
- **Lines** that cross the boundary are kept whole, because Turf has no
  line-polygon clip. That is an approximation and is stated rather than hidden.

### It applies to everything

The clip is one setting and everything obeys it. That was not true at first —
it governed the tools and the OpenStreetMap fetches and nothing else, which
made it a half-truth and the numbers beside it misleading.

| Where | What the clip does |
| --- | --- |
| Tools | The output is cut to the boundary before it is drawn |
| Live OpenStreetMap | Fetched features outside it are dropped |
| Query results | Rows whose geometry falls outside are not drawn, and the count says how many |
| Earth Engine layers | The raster is clipped server-side, so one district is a hundredth of the work of the whole country |
| Earth Engine summaries | Only zones inside the clip are reduced, so the table holds the rows you asked for |
| Ask | The agent can read the clip and set it, and is told to read it before interpreting any result |

Because it governs work started from several panels, the current clip is in the
status bar at all times, and shown again on each panel that starts work. A
number read without knowing what it covers is the thing this is guarding
against.

For Earth Engine the named boundaries come from geoBoundaries server-side — the
same source the summaries reduce onto — so a layer and the numbers taken from
it are cut from exactly the same shape.

The tool reports what happened: how many features fell inside, how many were
dropped, and which boundary was used. If nothing survives, it says so and
suggests widening rather than drawing an empty layer.
