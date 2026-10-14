# The ribbon

The viewer is laid out the way ArcGIS Pro is: a tab strip across the top, a
band of groups under it, and every control running one command.

That is not an aesthetic choice. Most people doing GIS in Ghana learned it in
ArcGIS Pro or QGIS — in the universities, in the Lands Commission, in the
district assemblies, in the NGOs. A tool that puts Clip under *Analyze →
Geoprocessing* and the layer list on the left needs no explaining to any of
them. A tool that invents its own arrangement asks every one of them to learn
it first.

The shape is borrowed from [RustGIS](https://github.com/rustgis/rustgis), whose
ribbon is itself ArcGIS Pro's: ten tabs, groups within them, and a command
registry underneath. RustGIS is Rust compiled to WebAssembly and this is a
single HTML page, so none of its code could be reused — what was taken is the
architecture, which was the part worth taking.

The whole of the arrangement is here, not the part this viewer can currently
perform. **109 groups, 395 controls, 390 commands.** A tool missing from the
place it belongs reads as *this cannot do that*; the honest answer is *not
yet*, and the way to say it is to leave the tool where a person would look for
it and mark it.

---

## The ten tabs

| Tab | Holds |
| --- | --- |
| **Home** | Navigate, add data, select, inspect — what you reach for every session |
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

## One command, one id

Every control — on the ribbon, in command search, in a keyboard shortcut, in
anything a plugin adds later — runs the same way:

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

There are **322 of them**, against 68 that are built, and they are shown rather
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

with the matching commands in `COMMANDS`. That is the whole of it — which is
the point of a registry, and why the ribbon was built this way rather than as
markup.

---

## Where the names come from

Command ids follow RustGIS wherever its ribbon names a single control, so its
`crates/ui-egui/src/ribbon.rs` reads as a reference implementation: a
contributor who wants to know what `layout.mapFrame` ought to do can see one
that works. Where RustGIS routes several controls through one dispatcher —
`ui.dialog`, `tool.set` — the arguments were doing the identifying, so those
became ids of their own.

The namespaces are `map`, `layer`, `data`, `table`, `style`, `labels`, `raster`,
`edit`, `graphics`, `select`, `gp`, `task`, `view`, `layout`, `report`,
`presentation`, `animation`, `publish`, `offline`, `cache`, `plugins`,
`settings`, `bookmark` and `ui`.

---

## A note on width

Some tabs are wider than a screen — Publish carries 25 groups. ArcGIS Pro
collapses a group into a single drop-down when it runs out of room; this does
not, yet. The band scrolls sideways with the wheel, and **Ctrl K** reaches any
command without hunting for its tab at all. Group collapsing is
`ui.ribbonCollapseGroups`, and it is open.
