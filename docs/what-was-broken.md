# What was broken, and how it stays fixed

Six faults found in one pass. They are written down because of what they have
in common: every one of them failed *silently*. The layer appeared, the log
said it had been added, the button responded to the click — and nothing
happened. A crash is a bug report; this kind is an afternoon.

Each now has a test, and the tests are the point of the page.

---

## Rasters never drew

**What it looked like.** Add *Active fire detections* from the data library.
It appears in Contents marked `raster`, it appears in the symbology, the log
says the layer was added. The map stays empty.

**What it was.** The Content-Security-Policy listed
`gibs.earthdata.nasa.gov` under `img-src` and not under `connect-src`. That
reads as correct — tiles are images — but MapLibre GL does not load raster
tiles with an `<img>` tag. It fetches them. So `connect-src` is the directive
that governs, and every NASA tile was refused before it left the browser. The
refusal went to the console, which the application never read.

**How it stays fixed.** `tests/test_csp.py` reads every `https://` host out of
`web/index.html` and fails if one is missing from `connect-src`, and fails if
a tile host is missing from either directive.

---

## No geoprocessing tool had ever run

**What it looked like.** Open the toolbox, choose a tool, fill the form, press
Run. Nothing.

**What it was.** `runToolboxTool` logged its arguments through a function
called `jsonSafe`, which is defined nowhere in the file. A `ReferenceError`
on the first statement of every run — and outside the `try` below it, so it
surfaced as the whole toolbox being inert rather than as one tool failing.

**Why it lasted.** The tools import Turf from a CDN, so no machine without
that CDN could run one, so the toolbox was the only part of the viewer with
no test at all.

**How it stays fixed.** `tests/turf_stub.cjs` substitutes the geometry
library, documenting precisely which of its functions are exact — centroid,
bbox, haversine distance, point-in-polygon, convex hull, nearest point — and
which are approximations that no assertion may rest on. `tests/toolbox.cjs`
then runs three tools end to end on a dropped layer and checks the result
becomes a layer that the next tool can take.

---

## Closing the layer list took the map with it

**What it looked like.** Press the Layers button. The map, and everything
drawn on it, disappears. The status bar still reports a zoom and an extent.

**What it was.** The workspace is a three-column grid: Contents, map, pane.
Hiding a dock takes it out of the flow, and with no column named explicitly
the map slid by auto-placement into the `auto` track the dock had vacated. An
`auto` track is as wide as its contents, and the map's only child is
absolutely positioned — so its contents are nothing. The map became zero
pixels wide.

**How it stays fixed.** Each dock owns a numbered column. `tests/ribbon.cjs`
closes the layer list and fails if the map does not get *wider*.

A second part of the same fault: a WebGL canvas has its size baked in, so
even with the column right the canvas had to be told. A `ResizeObserver` on
the map now handles every cause at once — docks, the ribbon collapsing, the
attribute table, full screen, the window — rather than a `resize()` call at
each of the dozen places that can change the layout, where the thirteenth
would have been forgotten.

---

## A dropped file opened in the browser

**What it looked like.** Drag a GeoJSON onto the window. The page navigates
away to the raw file, and the session is gone.

**What it was.** The drop handler was on the map element alone. Let go two
pixels into the layer list, or over the ribbon, or over the status bar, and
the browser's own default took it — and the browser's default for a dropped
file is to open it.

**How it stays fixed.** The window takes the drop and prevents the default
everywhere. `tests/adddata.cjs` dispatches a real `DragEvent` onto the
**ribbon** — about as far from the map as the window allows — and fails if
the drop was not accepted or no layer arrived.

---

## Attribute Table opened the SQL workspace

**What it looked like.** A button named *Attribute Table*, which opened the
SQL pane and typed a comment into it.

**What it was.** Exactly that. It had never been built.

**How it stays fixed.** There is a real table now, docked under the map —
see [The map interface](interface.md#the-attribute-table). `tests/table.cjs`
opens it on a dropped layer and checks the rows, the inferred column types,
that a number column sorts as numbers, that the filter filters, and that a
clicked row lights up on the map.

---

## A region boundary with no database threw a null

**What it looked like.** Clip to Ashanti without the database running:
*It failed: Cannot read properties of null (reading 'query')*.

**What it was.** `boundaryFeature` went straight to `conn.query` without
checking that there was a connection.

**How it stays fixed.** It now says which boundary could not be resolved and
what to use instead. `tests/toolbox.cjs` runs that exact case and fails if the
message is not in words.

---

## The pattern

Five of the six were invisible. The sixth — the null — at least said
something, and it said the wrong thing to the wrong audience.

The common cause is that each of these lived in a seam between two things
that were separately tested: the policy and the page, the toolbox and the
geometry library, the grid and the canvas, the drop handler and the browser's
default. Every new test here crosses a seam rather than checking a unit, and
each one failed the first time it was run, which is the only real evidence
that a test is worth having.
