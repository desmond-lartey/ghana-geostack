# The map interface

The viewer is laid out as a desktop GIS rather than as a web page with a map on
it: a ribbon across the top, a status bar along the bottom, the map filling
everything between them, and panels floating over it that can each be put away.
The ribbon has [its own page](ribbon.md); this one covers the rest of the frame.
Geoprocessing is a floating toolbox opened from the **Processing** menu, not a
tab competing with everything else.

That shape is borrowed from [GeoLibre](https://github.com/ArcaneDiver/geolibre),
and borrowed deliberately. Anyone who has used QGIS, ArcGIS or GeoLibre already
knows where to look, and a layout people already know needs no explaining.

---

## The parts

```
┌────────────────────────────────────────────────────────────────┐
│ Home  Data  Style  Edit  Analyze  View  Publish  …   🔍 Ctrl K │  tab strip
│ ┌─ Navigate ──┐┌─ Add Data ───┐┌─ Selection ─┐┌─ Inspect ──┐  │  ribbon
│ │ ▣ ▣ ▣ ▣ ▣ ▣ ││ ▣ ▣ ▣ ▣ ▣ ▣  ││ ▣ ▣ ▣       ││ ▣ ▣ ▣ ▣    │  │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────┐                        ▣ ▣ ▣ ▣ ▣ ▣  ← toolbar │
│ │ Layers     ×│                       ┌──────────────┐         │
│ │  ▸ card     │                       │ Style      × │         │
│ │  ▸ card     │          map          │              │         │
│ │ ────────────│                       │              │         │
│ │ 🔍 search   │   ┌────────────┐      │              │         │
│ └──────────────┘  │  legend    │      └──────────────┘         │
│                   └────────────┘                               │
├────────────────────────────────────────────────────────────────┤
│ Coords  Zoom  Scale  BBox  Eye alt  Bearing  Pitch │ CRS Clip  │  status bar
└────────────────────────────────────────────────────────────────┘
```

**The ribbon** holds everything the viewer can do: ten tabs, groups within
them, and every control running one named command. It has
[its own page](ribbon.md). **Ctrl K** searches all 390 commands by name, which
is how to find a tool when you know what it is called and not which tab it is
on.

**The toolbar** sits on the map at the top right. The left half is the map
itself — zoom in, zoom out, a compass whose needle turns with the map and puts
north back up when pressed, a globe/flat toggle, full screen, and the map
image export. The right half is one button per panel, each closing the panel it
opened. It stays in the same place whatever is open, because a control that
moves is a control to hunt for.

**The panels float on the map** rather than taking columns out of it. Layers on
the left, everything else on the right — Style, Data, the SQL workspace, Ask,
the Log, Basemap, Add data, Bookmarks, Identify, one at a time. Both can be
closed, from the toolbar or from the × in their own header, and with both
closed the map has the whole window. The map underneath is continuous, so a
drag does not stop at a panel's edge.

A ribbon button that names a panel opens it. It does not toggle it shut, which
it used to: pressing **AI Assistant** from the Analyze tab, with Ask already
the open pane, closed the pane you were asking for — and from a tab where the
dock is not necessarily in view, that reads as a button that does nothing.
Toggling is right for the dock's own tab strip, where the button is the tab,
and wrong from anywhere else.

**The status bar** reports where the map is. It is read, not operated, apart
from the clip.

---

## Layer cards

Each layer this session added is a card, newest at the top, and the card carries
everything that layer can have done to it:

| | |
| --- | --- |
| Eye | Show or hide, without losing it |
| Opacity | Fades the layer, whatever type it is |
| **↑ ↓** | Move it in front of or behind the others |
| **Zoom** | Fit the map to that layer's extent |
| **Style** | Open the right dock on this layer |
| **Table** | Open its rows in the SQL workspace |
| **Info** | Where it came from, and when |
| **Remove** | Take it off the map and free its source |

Selecting a card highlights it and expands its actions. One card is selected at
a time, and that is the layer the toolbox offers first.

Underneath, a producer registers its layer once — a label, its layer ids, an
extent, a colour, and a legend if it has one — and everything above follows from
that. A new kind of output is managed for free rather than needing controls of
its own.

The opacity slider reads each layer's type and sets the matching paint
property — `raster-opacity`, `fill-opacity`, `circle-opacity` — rather than
assuming. A source is removed only once nothing else draws from it.

Below them, the published layers are listed in their own groups — Administrative,
Infrastructure, Services, Analysis — each with a switch. Every one is listed,
including those that need the database running, which are marked and disabled
rather than hidden: a layer missing from a list looks like a layer that does
not exist.

Districts and Regions are drawn from GeoJSON when there is no database, so they
work in any deployment. They were the conspicuous omission from an earlier
version of this list — on the map, absent from the panel, and therefore
impossible to turn off.

---

## The search box

One box at the foot of the layer dock, for three questions that all end the
same way: *show me that*.

- **A layer name** selects that card and fits the map to it.
- **A region, district or capital** flies the map to its real extent, looked up
  in the boundaries rather than guessed.
- **A coordinate pair** — `6.67, -1.62` — goes straight there. Latitude first,
  as people write it, unless the first number cannot be a latitude.

Which of the three it is can be told from what was typed, so there is no mode
to set first.

---

## Adding your own data

**Home → Add Data → Add a File**, or drop the file anywhere on the map. The
pane holds a drop zone, a file picker, an address box for anything served over
HTTP, and a line of status that says what happened to each file.

Dropping works over the whole map, not only over the pane — the map dims and
says *Drop to add it to the map* while a file is over it — because the obvious thing to do
with a file is drag it onto the map, and a drop target the size of a panel
means finding the panel first.

Six formats, read in the browser with no server involved:

| | |
| --- | --- |
| **GeoJSON** | `.geojson`, or `.json` that parses as one. A FeatureCollection, a single Feature, or a bare geometry |
| **CSV / TSV** | Delimiter detected from the file. Quoted fields with commas in them are handled |
| **GPX** | Waypoints, routes and tracks |
| **KML** | Placemarks, including polygons and lines |
| **WKT in a CSV** | A geometry column written as `POINT(...)`, `POLYGON(...)` and so on |
| **Shapefile** | A `.zip` holding `.shp`, `.dbf` and friends. The reader is fetched on first use and not before, because most sessions never open one |

A CSV's coordinate columns are found by name — `lon`/`lat`, `x`/`y`,
`longitude`/`latitude`, `easting`/`northing`, or a WKT column. If none of them
are there, the error says so and lists the columns the file actually has,
which is more use than *could not read file*.

A row with an empty coordinate cell is dropped and counted, not placed.
`Number("")` is `0`, so the obvious code puts such a row at 0°N 0°E — which is
in the Gulf of Guinea, about 600 km south of Accra, close enough to Ghana to
look like data rather than a bug. The status line reports it: *towns.csv — 2 of
3 rows · 1 without a coordinate*.

What arrives becomes a layer card like any other, with fill, line and circle
styling for whichever geometries are in it, and the map fits to its extent. It
is also registered in the browser database as `ghana.add_<name>`, with the
file's own columns plus `lon`, `lat` and the geometry as GeoJSON text, so what
you dropped can be queried in the SQL workspace rather than only looked at:

```sql
select district, count(*) as towns, sum(people) as people
from ghana.add_towns
group by district
order by people desc;
```

That is the difference between a picture of your data and your data.

A file that cannot be read adds nothing and says why. It does not add an empty
layer, which looks like success.

---

## Basemaps

**View → Map → Basemap** opens a gallery of thirteen, grouped by what they are
for. None needs an API key or an account, which is the point: a key is a thing
to obtain, store and eventually have expire, and a platform meant to be
deployed by anyone cannot start with one.

| Group | |
| --- | --- |
| Reference | Esri Light Gray, Esri Dark Gray, CARTO Positron, CARTO Dark Matter, no basemap |
| Imagery | Esri World Imagery, and the same with labels over it |
| Street | OpenStreetMap, OSM Humanitarian, CARTO Voyager |
| Terrain | OpenTopoMap, Esri Topographic, Esri Ocean |

A grey reference basemap is the default and the right default: a choropleth
drawn over satellite imagery is unreadable, and the thing being mapped should
be the loudest thing on the screen. The imagery styles are there for when the
imagery *is* the subject — checking a building footprint, siting a borehole.
OSM Humanitarian is included because it draws the things humanitarian mapping
cares about, which is also much of what district planning cares about.

**Add your own** takes an XYZ template — `https://…/{z}/{x}/{y}.png` — and
checks it has the three placeholders before trying it. Any tile server that
serves plain XYZ works, including one on a laptop. Each entry carries its
provider's attribution, which is drawn on the map and written into an exported
map image, because every one of these services requires it.

Changing the basemap keeps everything you have added. This needs saying
because it did not: swapping the basemap replaces the whole MapLibre style,
which removes every source and layer on the map at once, and the catalogue
layers were rebuilt afterwards while the session's own were not. Picking a
different background threw away your dropped CSV, your buffer and your Earth
Engine raster, and the map came back looking perfectly fine — which is the
worst version of that, because what is missing is only noticed later. Each
added layer is now lifted out of the live style before the swap and put back on
top of the new basemap, in the order it had, and `tests/adddata.cjs` counts
what is drawn before and after to keep it that way.

---

## The legend

The legend sits at the bottom left of the map, and it is only there when there
is something to explain. It describes what is *drawn*, which is not the same as
what is in the layer list — a layer switched off explains nothing.

A layer coloured by a value comes first, names the column, and lists its
classes: a swatch and a range for each, the way QGIS and ArcGIS write a
graduated legend. The map draws those same classes — a `step` expression, not a
smooth interpolation — so a colour on the map can be found in the legend and
read off as a range. A gradient cannot be read that way at all, which is why
this changed.

Classes are equal count by default, which QGIS calls quantile: the same number
of features in each, so the whole palette is used even when the data is skewed,
and rainfall is skewed. Breaks are rounded to what a person would write down,
since an unrounded break is honest to five decimal places and unreadable.

A classified raster brings the producer's own class table with it, so ESA
WorldCover is listed class by class in the producer's colours. A continuous
raster shows its ramp with the minimum and maximum it was stretched to. Every
other drawn layer is one row under *On the map*, so the legend is a list of
what is on the map rather than a list of what happens to have a colour. A layer
that has its own group is not repeated as a swatch. The reference boundaries
keep the legend they were written with.

---

## Exporting a map image

**Project → Map image…**, or the picture button in the toolbar. A screenshot of
a web map is a picture of a browser; what a report needs is a map, so this
draws a print layout: a frame, a title and subtitle, a north arrow that turns
with the map, a scale bar rounded to a distance someone would write, the legend
with the classes the map is drawing, and the attributions the licences require.

Four shapes — landscape, portrait, square and a 16:9 slide — drawn at twice the
nominal size so the type stays sharp in print. The frame takes the middle of
the current view at the shape chosen, so panning and zooming until it looks
right is the composition step; what is on screen is what is drawn.

The map image comes from the live WebGL canvas, which is why the map is built
with `preserveDrawingBuffer`. Without it the buffer is cleared after each frame
and the export is a blank rectangle.

---

## The toolbox

**Processing → Ghana Toolbox** opens a floating window: a search box, a category
filter, the tool list on the left, and the chosen tool's parameters on the
right. It can be dragged out of the way, and the map stays live underneath it,
so a tool can be run, looked at, and run again with a different parameter
without anything closing.

Every tool declares its own parameters — what kind each one is, whether it is
required, what it means — and the form is generated from that declaration, which
is also what validates the form before a run. Adding a tool is one entry.

| Category | Tools |
| --- | --- |
| Vector — Overlay Analysis | Clip, Dissolve |
| Vector — Geometry | Centroids, Point on feature, Convex hull, Bounding box, Simplify, Measure |
| Vector — Proximity | Buffer, Voronoi catchments, Distance to nearest |
| Raster — Terrain | Sample elevation |

**Clip is a tool**, first in *Vector — Overlay Analysis*, because cutting one
layer to a boundary is an operation with an input and an output like any other.
It is also a setting that governs everything else — see
[Layers and clipping](layers-and-clipping.md) — and those two are not in
conflict: the setting decides what new work covers, the tool cuts something that
already exists.

Each run writes its own layer, so results stack instead of replacing one
another. Run a buffer at 2 km and again at 5 km and you have both, on the map
together, each removable on its own.

---

## What the status bar shows

| | |
| --- | --- |
| Coords | Longitude and latitude under the pointer |
| Zoom | The map's zoom level, to two decimals |
| Scale | How wide the view is on the ground |
| BBox | The visible extent, ready to paste into a query |
| Eye alt | How far up the camera is, from the view rather than the zoom number |
| Bearing, Pitch | Rotation and tilt, in degrees |
| CRS | `EPSG:4326`, and which projection is drawing it |
| Clip | What analyses are currently confined to |
| Layers | How many this session has added |

The clip is there because a number read without knowing what it covers is the
thing this whole design is guarding against.
