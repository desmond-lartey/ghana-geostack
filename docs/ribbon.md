# The ribbon

The viewer is laid out the way ArcGIS Pro is: a tab strip across the top, a
band of groups under it, and every control running one command.

That is not an aesthetic choice. Most people doing GIS in Ghana learned it in
ArcGIS Pro or QGIS - in the universities, in the Lands Commission, in the
district assemblies, in the NGOs. A tool that puts Clip under *Analyze →
Geoprocessing* and the layer list on the left needs no explaining to any of
them. A tool that invents its own arrangement asks every one of them to learn
it first.

The shape is borrowed from [RustGIS](https://github.com/rustgis/rustgis), whose
ribbon is itself ArcGIS Pro's: ten tabs, groups within them, and a command
registry underneath. RustGIS is Rust compiled to WebAssembly and this is a
single HTML page, so none of its code could be reused - what was taken is the
architecture, which was the part worth taking.

The whole of the arrangement is here, not the part this viewer can currently
perform. **10 tabs, 77 groups, 406 controls, 401 commands.** A tool missing
from the place it belongs reads as *this cannot do that*; the honest answer is
*not yet*, and the way to say it is to leave the tool where a person would look
for it and mark it.

---

## The ten tabs

| Tab | Holds |
| --- | --- |
| **Home** | The Ghana data library, navigate, add data, select, inspect - what you reach for every session |
| **Data** | The catalogue, database connections, tables, definition queries, export |
| **Style** | Symbology, classification, labels, effects, raster rendering |
| **Edit** | Editing, drawing, snapping, the clipboard |
| **Analyze** | Geoprocessing, vector and raster tools, statistics, the assistant |
| **View** | Panels, the map frame, what is drawn on it, windows |
| **Publish** | The map image, data export, sharing, reports |
| **Plugins** | Community plugins and task automation |
| **Settings** | Interface, language, units, coordinate system, privacy |
| **Help** | The tour, documentation, and how to contribute |

---

## Ghana Data comes first

The first group on the Home tab is **Ghana Data**, and the first control in it
is the [Ghana data library](library.md): thirty-five layers for Ghana as
cards, with a picture, a source, a licence and a plain statement of whether
each can be drawn right now. Beside it are eleven themed buttons that open the
same library already narrowed - Boundaries, Population, Health, Education,
Water, Transport, Agriculture, Climate, Flood and fire, Energy.

It is first because the Home tab's job is to answer *where do I start*, and
for anyone opening this for the first time the answer is "see what there is".
Everything else on Home - Navigate, Add Data, Selection, Inspect - assumes you
already have something on the map.

---

## One set of groups, not two

The working parts of this viewer sit *inside* the ArcGIS-shaped groups, not
beside them. An earlier arrangement had both: ArcGIS Pro's *Add Data* group
and, further along the same tab, a second group holding this viewer's own
catalogue and OpenStreetMap buttons. Two groups for one job, with the thing
you wanted in whichever of them you looked at second.

Folding them left 76 groups where there had been 109, with no name repeated on
any tab, and the controls that actually run something first within each group.
So **Home → Add Data** is one group, and what is in it is this:

| | |
| --- | --- |
| Earth Observation | The catalogue of Earth Engine collections |
| Health Facilities, Schools, Water Points, Markets, Roads, Buildings | Live OpenStreetMap fetches, clipped to the current clip |
| Add a File, Add from URL | The [Add data](interface.md#adding-your-own-data) pane |
| Add WMS / WMTS, Sample Data | A served layer, and the bundled examples |
| Delimited Text…, Graphics Layer | Open |

The same fold runs through the rest. **Home → Navigate** holds this page's
pan, zoom, extent history, compass and go-to-coordinate; **Home → Inspect**
holds Identify, Measure, the attribute table and the SQL workspace;
**Analyze → Geoprocessing** opens the toolbox described in
[The map interface](interface.md#the-toolbox); **Analyze → Assistant** opens
the agent; **View → Panels** is one button per dock pane; **View → Map** holds
the basemap gallery, the globe/flat toggle, terrain, the light and dark themes,
Find Me and full screen.

The rule for the fold was that a group keeps ArcGIS Pro's name, because the
name is what people are looking for, and gains this viewer's controls at the
top of it, because a group whose first three buttons are open slots reads as
an empty group.

---

## A button that does nothing is a bug

Every control on the ribbon falls into one of two cases, and there is no third.
Either it is **built**, and pressing it does the thing; or it is an **open
slot**, and pressing it says so - what the command is for, what it is called,
and where in the source to write it. What used not to happen, and now cannot,
is a built control that appears to do nothing.

The cause was the ribbon's panel commands toggling. **AI Assistant** ran
`showPanel("ask", { toggle: true })`, which closes the pane if it is already
the open one - correct for the dock's own tab strip, where the button you press
is the tab you can see, and wrong for a ribbon button three tabs away from the
dock. Press it with Ask already open and the pane closed; press it again and it
opened; from the Analyze tab, where the dock is not necessarily in view, both
looked like nothing happening. Six commands did this. They now show the pane
rather than toggling it, so a ribbon button that names a panel always ends with
that panel open.

`tests/ribbon.cjs` runs every built command and fails on the first one that
throws, which catches the other half of the same promise.

---

## One command, one id

Every control - on the ribbon, in command search, in a keyboard shortcut, in
anything a plugin adds later - runs the same way:

```js
runCommand("gp.buffer");
```

The registry is a single object in `web/index.html`:

```js
"gp.buffer": {
  id: "gp.buffer",
  label: "Buffer",
  desc: "A zone of the given radius around each feature.",
  icon: "buffer",
  run: () => openToolbox("", "buffer")
}
```

and the ribbon is declared as data beside it:

```js
{ group: "Geoprocessing", controls: [
  { cmd: "gp.toolbox", size: "big" },
  { cmd: "gp.buffer",  size: "small" }
] }
```

The ribbon is rendered from that, not written as markup. Three hundred
hand-written buttons is three hundred places for a label and its behaviour to
drift apart, and it makes adding a command a change in two files instead of
one.

**Ctrl K** opens command search, which is how you find a tool when you know its
name and not its tab.

---

## Open slots

A command with no `run` is a slot. The ribbon, the registry and the place it
plugs into are built; the function behind it is not.

There are **316 of them**, against 85 that are built, and they are shown rather
than hidden: a gold dot on the control, and pressing it says what the command
is for, what it is called, and where to write it. The full list, generated from
the registry so it cannot go stale, is in
[the command reference](commands.md).

This is deliberate. Ghana GeoStack is meant to be finished by the people who
use it, and an empty slot with a name and an address is an invitation where a
hidden one is nothing at all. Each is a small, self-contained job with no
architecture to design first:

1. Find the command in the `COMMANDS` registry in `web/index.html`.
2. Add a `run`.
3. Nothing else. The button, its icon, its tooltip and its place on the tab are
   already declared, and `tests/ribbon.cjs` will run your command along with
   every other built one.

A slot that turns out to be the wrong idea is also useful information, and
deleting one is two lines.

---

## Adding a tab

A group is one entry in `RIBBON`; a tab is one more:

```js
{ tab: "Hydrology", groups: [
  { group: "Catchments", controls: [
    { cmd: "hydro.delineate", size: "big" }
  ] }
] }
```

with the matching commands in `COMMANDS`. That is the whole of it - which is
the point of a registry, and why the ribbon was built this way rather than as
markup.

---

## Where the names come from

Command ids follow RustGIS wherever its ribbon names a single control, so its
`crates/ui-egui/src/ribbon.rs` reads as a reference implementation: a
contributor who wants to know what `layout.mapFrame` ought to do can see one
that works. Where RustGIS routes several controls through one dispatcher -
`ui.dialog`, `tool.set` - the arguments were doing the identifying, so those
became ids of their own.

The namespaces are `map`, `layer`, `data`, `table`, `style`, `labels`, `raster`,
`edit`, `graphics`, `select`, `gp`, `task`, `view`, `layout`, `report`,
`presentation`, `animation`, `publish`, `offline`, `cache`, `plugins`,
`settings`, `bookmark` and `ui`.

---

## A note on width

Some tabs are wider than a screen - Publish carries 12 groups and 87
controls, Analyze 14 groups. ArcGIS Pro
collapses a group into a single drop-down when it runs out of room; this does
not, yet. The band scrolls sideways with the wheel, and **Ctrl K** reaches any
command without hunting for its tab at all.

A chevron appears at whichever end of the band has something that way, and
scrolls it by six tenths of a view. RustGIS puts the same button in the same
place, for the reason its source gives: the scroll bar would sit across the
group labels, and the wheel alone is undiscoverable. Nothing on screen said
the band moved, so a tab with twelve groups read as a tab with four. Group
collapsing - folding a group into a single drop-down the way ArcGIS Pro does
when it runs out of room - is still open, as `ui.ribbonCollapseGroups`.

A ribbon wider than the screen used to widen the whole window with it. The
shell is a CSS grid, and a grid item's `min-width` is `auto` - a track of `1fr`
is still at least as wide as its widest content, so the Publish band stretched
the column it sat in, and the column was the application. The right-hand dock
and the map toolbar were measured at x=4318 in a 1600-pixel window: present,
correct, and several thousand pixels off the side of the screen. The track is
`minmax(0, 1fr)` now, with `min-width: 0` on the ribbon and the workspace, so
the band scrolls inside a shell that stays the size of the window.
`tests/ribbon.cjs` clicks every tab and asserts the dock is still on screen,
because this failed in a way that looked like the panels had disappeared.
