# The map interface

The viewer is laid out as a desktop GIS rather than as a web page with a map on
it: a menu bar across the top, a status bar along the bottom, the map filling
everything between them, and panels floating over it that can each be put away.
Geoprocessing is a floating toolbox opened from the **Processing** menu, not a
tab competing with everything else.

That shape is borrowed from [GeoLibre](https://github.com/ArcaneDiver/geolibre),
and borrowed deliberately. Anyone who has used QGIS, ArcGIS or GeoLibre already
knows where to look, and a layout people already know needs no explaining.

---

## The parts

```
┌────────────────────────────────────────────────────────────────┐
│ Ghana GeoStack   Project  View  Add Data  Processing  Help     │  menu bar
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

**The menu bar** holds everything the viewer can do, grouped by what it is for.
*Project* is data and exports, *View* is the map itself, *Add Data* brings
something new in, *Processing* opens the toolbox, *Help* explains the place.

**The toolbar** sits on the map at the top right: one button per panel, and
each one closes the panel it opened. It stays in the same place whatever is
open, because a control that moves is a control to hunt for.

**The panels float on the map** rather than taking columns out of it. Layers on
the left, everything else on the right — Style, Data, the SQL workspace, Ask,
the Log, one at a time. Both can be closed, from the toolbar or from the × in
their own header, and with both closed the map has the whole window. The map
underneath is continuous, so a drag does not stop at a panel's edge.

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

## The legend

The legend sits at the bottom left of the map, and it is only there when there
is something to explain. It describes what is *drawn*, which is not the same as
what is in the layer list — a layer switched off explains nothing.

A classified raster brings the producer's own class table with it, so ESA
WorldCover is listed class by class in the producer's colours. A continuous
raster shows its ramp with the minimum and maximum it was stretched to. Anything
else is one swatch. The reference boundaries keep the legend they were written
with.

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
